from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.runtime import AppContext
from app.models.automation import AutomationRuleRecord
from app.repositories.automation import AutomationRepository


@dataclass(slots=True)
class AutomationTemplate:
    key: str
    name: str
    schedule_key: str
    description: str


TEMPLATES: tuple[AutomationTemplate, ...] = (
    AutomationTemplate(
        key="DAILY_REPORT",
        name="Daily Report Delivery",
        schedule_key="DAILY",
        description="Sends the daily ops report to owners every 24 hours.",
    ),
    AutomationTemplate(
        key="WEEKLY_REPORT",
        name="Weekly Report Delivery",
        schedule_key="WEEKLY",
        description="Sends the weekly ops summary to owners every 7 days.",
    ),
    AutomationTemplate(
        key="BOT_HEALTH_CHECK",
        name="Bot Health Watch",
        schedule_key="EVERY_6_HOURS",
        description="Checks managed bot health URLs and alerts owners when bots degrade.",
    ),
    AutomationTemplate(
        key="PENDING_REVIEW_WATCH",
        name="Pending Review Watch",
        schedule_key="EVERY_2_HOURS",
        description="Alerts owners when pending channels or groups are waiting for approval.",
    ),
    AutomationTemplate(
        key="FAILED_SCHEDULE_WATCH",
        name="Failed Schedule Watch",
        schedule_key="EVERY_2_HOURS",
        description="Alerts owners when scheduled posts fail to publish.",
    ),
)


class AutomationService:
    CONDITION_TRIGGER_KEYS = {
        "PENDING_REVIEW",
        "PENDING_CHANNELS",
        "PENDING_GROUPS",
        "FAILED_SCHEDULES",
        "OFFLINE_BOTS",
        "DEGRADED_BOTS",
        "PAUSED_RECURRING_SCHEDULES",
    }

    def __init__(self, app_context: AppContext) -> None:
        self.app_context = app_context

    def list_templates(self) -> tuple[AutomationTemplate, ...]:
        return TEMPLATES

    async def create_rule(self, template_key: str, created_by_user_id: int | None) -> AutomationRuleRecord | None:
        template = self.get_template(template_key)
        if not template or not self.app_context.oracle_client:
            return None

        repository = AutomationRepository(self.app_context.oracle_client)
        next_run_at = datetime.utcnow() + self._interval_for(template.schedule_key)
        return await asyncio.to_thread(
            repository.upsert_rule,
            template.key,
            template.name,
            template.schedule_key,
            None,
            "ACTIVE",
            created_by_user_id,
            next_run_at,
        )

    async def create_custom_owner_alert(
        self,
        *,
        rule_name: str,
        schedule_key: str,
        message_text: str,
        cooldown_minutes: int = 0,
        quiet_hours_start: int | None = None,
        quiet_hours_end: int | None = None,
        created_by_user_id: int | None,
    ) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        normalized_name = (rule_name or "").strip() or "Custom Owner Alert"
        normalized_schedule = schedule_key.strip().upper()
        if normalized_schedule not in {"DAILY", "WEEKLY", "EVERY_2_HOURS", "EVERY_6_HOURS"}:
            normalized_schedule = "DAILY"
        payload = json.dumps(
            {
                "kind": "CUSTOM_OWNER_ALERT",
                "message_text": message_text.strip(),
                "cooldown_minutes": max(0, int(cooldown_minutes or 0)),
                "quiet_hours_start": self._normalize_hour(quiet_hours_start),
                "quiet_hours_end": self._normalize_hour(quiet_hours_end),
            },
            ensure_ascii=True,
        )
        repository = AutomationRepository(self.app_context.oracle_client)
        template_key = f"CUSTOM_OWNER_ALERT_{int(datetime.utcnow().timestamp())}"
        next_run_at = datetime.utcnow() + self._interval_for(normalized_schedule)
        return await asyncio.to_thread(
            repository.create_rule,
            template_key,
            normalized_name,
            normalized_schedule,
            payload,
            "ACTIVE",
            created_by_user_id,
            next_run_at,
        )

    async def create_custom_condition_alert(
        self,
        *,
        rule_name: str,
        schedule_key: str,
        trigger_keys: list[str] | tuple[str, ...],
        threshold: int,
        message_text: str,
        cooldown_minutes: int = 0,
        quiet_hours_start: int | None = None,
        quiet_hours_end: int | None = None,
        created_by_user_id: int | None,
    ) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        normalized_name = (rule_name or "").strip() or "Conditional Owner Alert"
        normalized_schedule = schedule_key.strip().upper()
        if normalized_schedule not in {"DAILY", "WEEKLY", "EVERY_2_HOURS", "EVERY_6_HOURS"}:
            normalized_schedule = "EVERY_2_HOURS"
        normalized_triggers = [
            item.strip().upper()
            for item in trigger_keys
            if isinstance(item, str) and item.strip()
        ]
        normalized_triggers = [
            item for item in normalized_triggers if item in self.CONDITION_TRIGGER_KEYS
        ]
        if not normalized_triggers:
            normalized_triggers = ["PENDING_REVIEW"]
        normalized_threshold = max(1, int(threshold))
        payload = json.dumps(
            {
                "kind": "CUSTOM_CONDITION_ALERT",
                "trigger_keys": normalized_triggers,
                "threshold": normalized_threshold,
                "message_text": message_text.strip(),
                "cooldown_minutes": max(0, int(cooldown_minutes or 0)),
                "quiet_hours_start": self._normalize_hour(quiet_hours_start),
                "quiet_hours_end": self._normalize_hour(quiet_hours_end),
            },
            ensure_ascii=True,
        )
        repository = AutomationRepository(self.app_context.oracle_client)
        template_key = f"CUSTOM_CONDITION_ALERT_{int(datetime.utcnow().timestamp())}"
        next_run_at = datetime.utcnow() + self._interval_for(normalized_schedule)
        return await asyncio.to_thread(
            repository.create_rule,
            template_key,
            normalized_name,
            normalized_schedule,
            payload,
            "ACTIVE",
            created_by_user_id,
            next_run_at,
        )

    @staticmethod
    def parse_config(record: AutomationRuleRecord) -> dict[str, str]:
        if not record.config_json:
            return {}
        try:
            payload = json.loads(record.config_json)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    async def list_rules(self) -> list[AutomationRuleRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_rules)

    async def get_rule(self, rule_id: int) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.get_rule, rule_id)

    async def toggle_rule(self, rule_id: int) -> AutomationRuleRecord | None:
        record = await self.get_rule(rule_id)
        if not record or not self.app_context.oracle_client:
            return record
        repository = AutomationRepository(self.app_context.oracle_client)
        new_status = "PAUSED" if record.status == "ACTIVE" else "ACTIVE"
        updated = await asyncio.to_thread(repository.update_status, rule_id, new_status)
        if updated and updated.status == "ACTIVE":
            updated = await asyncio.to_thread(
                repository.update_next_run,
                updated.id,
                datetime.utcnow() + self._interval_for(updated.schedule_key),
            )
        return updated

    async def delete_rule(self, rule_id: int) -> bool:
        if not self.app_context.oracle_client:
            return False
        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.delete_rule, rule_id)

    async def duplicate_rule(self, rule_id: int, created_by_user_id: int | None) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        existing = await self.get_rule(rule_id)
        if not existing:
            return None

        repository = AutomationRepository(self.app_context.oracle_client)
        base_name = (existing.template_name or "Automation Rule").strip() or "Automation Rule"
        duplicate_name = f"{base_name} Copy"
        template_key = f"{existing.template_key}_COPY_{int(datetime.utcnow().timestamp())}"
        next_run_at = datetime.utcnow() + self._interval_for(existing.schedule_key)
        return await asyncio.to_thread(
            repository.create_rule,
            template_key,
            duplicate_name,
            existing.schedule_key,
            existing.config_json,
            "ACTIVE",
            created_by_user_id,
            next_run_at,
        )

    async def defer_rule(self, rule_id: int, next_run_at: datetime) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.update_next_run, rule_id, next_run_at)

    async def update_custom_rule(
        self,
        *,
        rule_id: int,
        rule_name: str,
        schedule_key: str,
        message_text: str,
        threshold: int | None = None,
        trigger_keys: list[str] | tuple[str, ...] | None = None,
        cooldown_minutes: int = 0,
        quiet_hours_start: int | None = None,
        quiet_hours_end: int | None = None,
    ) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client:
            return None
        existing = await self.get_rule(rule_id)
        if not existing:
            return None
        config = self.parse_config(existing)
        kind = str(config.get("kind", "")).strip().upper()
        if kind not in {"CUSTOM_OWNER_ALERT", "CUSTOM_CONDITION_ALERT"}:
            return None

        normalized_name = (rule_name or "").strip() or existing.template_name
        normalized_schedule = schedule_key.strip().upper()
        if normalized_schedule not in {"DAILY", "WEEKLY", "EVERY_2_HOURS", "EVERY_6_HOURS"}:
            normalized_schedule = existing.schedule_key

        payload: dict[str, object]
        if kind == "CUSTOM_OWNER_ALERT":
            payload = {
                "kind": kind,
                "message_text": message_text.strip(),
                "cooldown_minutes": max(0, int(cooldown_minutes or 0)),
                "quiet_hours_start": self._normalize_hour(quiet_hours_start),
                "quiet_hours_end": self._normalize_hour(quiet_hours_end),
            }
        else:
            normalized_threshold = max(1, int(threshold or config.get("threshold", 1) or 1))
            normalized_triggers = [
                str(item).strip().upper()
                for item in (trigger_keys or config.get("trigger_keys") or [])
                if str(item).strip()
            ]
            normalized_triggers = [
                item for item in normalized_triggers if item in self.CONDITION_TRIGGER_KEYS
            ]
            if not normalized_triggers:
                legacy_trigger = str(config.get("trigger_key", "")).strip().upper()
                normalized_triggers = (
                    [legacy_trigger]
                    if legacy_trigger in self.CONDITION_TRIGGER_KEYS
                    else ["PENDING_REVIEW"]
                )
            payload = {
                "kind": kind,
                "trigger_keys": normalized_triggers,
                "threshold": normalized_threshold,
                "message_text": message_text.strip(),
                "cooldown_minutes": max(0, int(cooldown_minutes or 0)),
                "quiet_hours_start": self._normalize_hour(quiet_hours_start),
                "quiet_hours_end": self._normalize_hour(quiet_hours_end),
            }

        next_run_at = existing.next_run_at
        if existing.status == "ACTIVE":
            next_run_at = datetime.utcnow() + self._interval_for(normalized_schedule)

        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.update_rule_definition,
            rule_id,
            normalized_name,
            normalized_schedule,
            json.dumps(payload, ensure_ascii=True),
            next_run_at,
        )

    async def list_due_rules(self) -> list[AutomationRuleRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = AutomationRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_due_rules, datetime.utcnow())

    async def mark_rule_run(self, record: AutomationRuleRecord) -> AutomationRuleRecord | None:
        if not self.app_context.oracle_client or not record.id:
            return record
        repository = AutomationRepository(self.app_context.oracle_client)
        now = datetime.utcnow()
        next_run_at = now + self._interval_for(record.schedule_key)
        return await asyncio.to_thread(repository.mark_run, record.id, now, next_run_at)

    def get_template(self, template_key: str) -> AutomationTemplate | None:
        for item in TEMPLATES:
            if item.key == template_key:
                return item
        return None

    @staticmethod
    def _interval_for(schedule_key: str) -> timedelta:
        mapping = {
            "DAILY": timedelta(days=1),
            "WEEKLY": timedelta(days=7),
            "EVERY_2_HOURS": timedelta(hours=2),
            "EVERY_6_HOURS": timedelta(hours=6),
        }
        return mapping.get(schedule_key, timedelta(days=1))

    @staticmethod
    def _normalize_hour(value: int | None) -> int | None:
        if value is None:
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= normalized <= 23:
            return normalized
        return None
