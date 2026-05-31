from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from app.core.runtime import AppContext
from app.db.redis_client import build_redis_client
from app.models.audit import AuditLogRecord
from app.repositories.audit import AuditRepository
from app.services.automation import AutomationService
from app.services.automation_utils import (
    normalize_trigger_keys,
    render_condition_message,
    safe_hour,
    should_run_custom_rule,
    summarize_items,
)
from app.services.bots import ManagedBotService
from app.services.entities import ManagedEntityService
from app.services.reports import ReportService
from app.services.schedule import ScheduleService

logger = logging.getLogger(__name__)


class AutomationRunner:
    def __init__(self, app_context: AppContext, bot: Bot, poll_interval_seconds: int = 60) -> None:
        self.app_context = app_context
        self.bot = bot
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        redis_client = build_redis_client(app_context.settings)
        self.automation_service = AutomationService(app_context)
        self.report_service = ReportService(app_context, redis_client=redis_client)
        self.bot_service = ManagedBotService(app_context, redis_client=redis_client)
        self.entity_service = ManagedEntityService(app_context, redis_client=redis_client)
        self.schedule_service = ScheduleService(app_context, redis_client=redis_client)

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._run_loop(), name="automation-runner")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None

    async def _run_loop(self) -> None:
        await asyncio.sleep(15)
        while not self._stop_event.is_set():
            try:
                await self._process_due_rules()
            except Exception:
                logger.exception("Automation runner loop failed")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _process_due_rules(self) -> None:
        due_rules = await self.automation_service.list_due_rules()
        for rule in due_rules:
            try:
                await self.run_rule_once(rule, mark_run=True)
            except Exception:
                logger.exception("Automation rule failed: %s", rule.template_key)

    async def run_rule_once(self, rule, *, mark_run: bool) -> None:
        try:
            was_run, defer_until = await self._run_rule(rule, bypass_guards=not mark_run)
            if not was_run:
                if mark_run and rule.id and defer_until:
                    await self.automation_service.defer_rule(rule.id, defer_until)
                    await self._record_run_event(
                        action_key="AUTOMATION_RUN_DEFERRED",
                        target_id=str(rule.id or rule.template_key),
                        details=f"{rule.template_key}|until={defer_until.isoformat()}",
                    )
                return
            if mark_run:
                await self.automation_service.mark_rule_run(rule)
            await self._record_run_event(
                action_key="AUTOMATION_RUN_OK",
                target_id=str(rule.id or rule.template_key),
                details=rule.template_key,
            )
        except Exception:
            await self._record_run_event(
                action_key="AUTOMATION_RUN_FAILED",
                target_id=str(rule.id or rule.template_key),
                details=rule.template_key,
            )
            raise

    async def _run_rule(self, rule, *, bypass_guards: bool) -> tuple[bool, datetime | None]:
        if rule.template_key == "DAILY_REPORT":
            bundle = await self.report_service.build_reports()
            await self._send_to_owners(bundle.daily_text)
            return True, None

        if rule.template_key == "WEEKLY_REPORT":
            bundle = await self.report_service.build_reports()
            await self._send_to_owners(bundle.weekly_text)
            return True, None

        if rule.template_key == "BOT_HEALTH_CHECK":
            records = await self.bot_service.list_bots()
            issues: list[str] = []
            for item in records:
                refreshed = await self.bot_service.refresh_status(item.id)
                if refreshed and refreshed.status != "ONLINE":
                    issues.append(
                        f"- {(refreshed.display_name or refreshed.bot_username)} -> {refreshed.status}"
                    )
            if issues:
                await self._send_to_owners("Bot health alert\n\n" + "\n".join(issues))
            return True, None

        if rule.template_key == "PENDING_REVIEW_WATCH":
            pending_channels = await self.entity_service.list_channels_by_status("PENDING")
            pending_groups = await self.entity_service.list_groups_by_status("PENDING")
            if pending_channels or pending_groups:
                lines = [
                    "Pending review alert",
                    "",
                    f"Pending channels: {len(pending_channels)}",
                    f"Pending groups: {len(pending_groups)}",
                ]
                for item in pending_channels[:5]:
                    lines.append(f"- Channel: {item.title or item.chat_identifier}")
                for item in pending_groups[:5]:
                    lines.append(f"- Group: {item.title or item.chat_identifier}")
                await self._send_to_owners("\n".join(lines))
            return True, None

        if rule.template_key == "FAILED_SCHEDULE_WATCH":
            failed_posts = await self.schedule_service.list_failed()
            if failed_posts:
                lines = [
                    "Failed schedule alert",
                    "",
                    f"Failed scheduled posts: {len(failed_posts)}",
                ]
                for item in failed_posts[:5]:
                    label = item.channel_title or item.channel_identifier
                    when = item.scheduled_for.strftime("%Y-%m-%d %H:%M") if item.scheduled_for else "unknown"
                    lines.append(f"- {label} | {when}")
                await self._send_to_owners("\n".join(lines))
            return True, None

        if rule.template_key.startswith("CUSTOM_OWNER_ALERT"):
            config = {}
            if rule.config_json:
                try:
                    config = json.loads(rule.config_json)
                except json.JSONDecodeError:
                    config = {}
            if not bypass_guards:
                should_run, defer_until = self._should_run_custom_rule(rule, config)
                if not should_run:
                    return False, defer_until
            message_text = str(config.get("message_text", "")).strip()
            if message_text:
                await self._send_to_owners(message_text)
            return True, None

        if rule.template_key.startswith("CUSTOM_CONDITION_ALERT"):
            config = {}
            if rule.config_json:
                try:
                    config = json.loads(rule.config_json)
                except json.JSONDecodeError:
                    config = {}
            if not bypass_guards:
                should_run, defer_until = self._should_run_custom_rule(rule, config)
                if not should_run:
                    return False, defer_until
            trigger_keys = normalize_trigger_keys(config)
            threshold = max(1, int(config.get("threshold", 1) or 1))
            message_text = str(config.get("message_text", "")).strip()

            matched_conditions: list[dict[str, str | int]] = []
            total_hit_count = 0
            for trigger_key in trigger_keys:
                hit_count, details = await self._evaluate_condition_trigger(trigger_key)
                if hit_count >= threshold:
                    matched_conditions.append(
                        {
                            "trigger_key": trigger_key,
                            "count": hit_count,
                            "details": details or "-",
                        }
                    )
                    total_hit_count += hit_count

            if matched_conditions and message_text:
                primary = matched_conditions[0]
                rendered_details = " | ".join(
                    f"{item['trigger_key']}={item['count']} [{item['details']}]"
                    for item in matched_conditions
                )
                rendered_message = render_condition_message(
                    message_text,
                    trigger_key=str(primary["trigger_key"]),
                    count=total_hit_count,
                    threshold=threshold,
                    details=rendered_details,
                )
                await self._send_to_owners(rendered_message)
                await self._record_run_event(
                    action_key="AUTOMATION_CONDITION_MATCH",
                    target_id=str(rule.id or rule.template_key),
                    details=f"triggers={','.join(trigger_keys)}|count={total_hit_count}|details={rendered_details}",
                )
            return True, None
        return True, None

    async def _evaluate_condition_trigger(self, trigger_key: str) -> tuple[int, str]:
        if trigger_key == "PENDING_REVIEW":
            pending_channels = await self.entity_service.list_channels_by_status("PENDING")
            pending_groups = await self.entity_service.list_groups_by_status("PENDING")
            return (
                len(pending_channels) + len(pending_groups),
                summarize_items(
                    [f"Channel: {item.title or item.chat_identifier}" for item in pending_channels]
                    + [f"Group: {item.title or item.chat_identifier}" for item in pending_groups]
                ),
            )
        if trigger_key == "PENDING_CHANNELS":
            pending_channels = await self.entity_service.list_channels_by_status("PENDING")
            return (
                len(pending_channels),
                summarize_items([item.title or item.chat_identifier for item in pending_channels]),
            )
        if trigger_key == "PENDING_GROUPS":
            pending_groups = await self.entity_service.list_groups_by_status("PENDING")
            return (
                len(pending_groups),
                summarize_items([item.title or item.chat_identifier for item in pending_groups]),
            )
        if trigger_key == "FAILED_SCHEDULES":
            failed_posts = await self.schedule_service.list_failed()
            return (
                len(failed_posts),
                summarize_items(
                    [
                        f"{item.channel_title or item.channel_identifier} @ {item.scheduled_for.strftime('%Y-%m-%d %H:%M') if item.scheduled_for else 'unknown'}"
                        for item in failed_posts
                    ]
                ),
            )
        if trigger_key == "OFFLINE_BOTS":
            records = await self.bot_service.list_bots()
            issues = [item for item in records if item.status in {"OFFLINE", "UNKNOWN"}]
            return (
                len(issues),
                summarize_items(
                    [f"{item.display_name or item.bot_username} -> {item.status}" for item in issues]
                ),
            )
        if trigger_key == "DEGRADED_BOTS":
            records = await self.bot_service.list_bots()
            issues = [item for item in records if item.status in {"DEGRADED", "UNKNOWN"}]
            return (
                len(issues),
                summarize_items(
                    [f"{item.display_name or item.bot_username} -> {item.status}" for item in issues]
                ),
            )
        if trigger_key == "PAUSED_RECURRING_SCHEDULES":
            paused_records = await self.schedule_service.list_paused()
            recurring_paused = [item for item in paused_records if item.recurrence_key]
            return (
                len(recurring_paused),
                summarize_items(
                    [f"{item.channel_title or item.channel_identifier} -> {item.recurrence_key}" for item in recurring_paused]
                ),
            )
        return 0, "-"

    def _should_run_custom_rule(self, rule, config: dict[str, object]) -> tuple[bool, datetime | None]:
        return should_run_custom_rule(
            last_run_at=rule.last_run_at,
            config=config,
            now_utc=datetime.utcnow(),
            dhaka_now=datetime.now(ZoneInfo("Asia/Dhaka")),
        )

    async def _send_to_owners(self, text: str) -> None:
        for owner_id in self.app_context.settings.owner_ids:
            try:
                await self.bot.send_message(owner_id, text)
            except Exception:
                logger.warning("Failed to send automation message to owner %s", owner_id)

    async def _record_run_event(self, action_key: str, target_id: str, details: str | None = None) -> None:
        if not self.app_context.oracle_client:
            return
        try:
            await asyncio.to_thread(
                AuditRepository(self.app_context.oracle_client).insert,
                AuditLogRecord(
                    actor_user_id=None,
                    action_key=action_key,
                    target_type="AUTOMATION",
                    target_id=target_id,
                    details=details,
                ),
            )
        except Exception:
            logger.exception("Failed to write automation audit event: %s", action_key)
