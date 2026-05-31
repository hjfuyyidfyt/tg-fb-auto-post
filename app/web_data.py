from __future__ import annotations

import asyncio
import csv
import io
import html
from datetime import datetime, timezone

from fastapi import FastAPI

from app.models.audit import AuditLogRecord
from app.repositories.audit import AuditRepository
from app.web_entities import load_bot_rows, load_entity_rows
from app.web_schedule import load_schedule_history_rows, load_schedule_rows


def escape_html(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def matches_filters(values: list[str], row_status: str, query: str, status_filter: str) -> bool:
    if status_filter != "ALL" and row_status.upper() != status_filter:
        return False
    if not query:
        return True
    haystack = " ".join(value.lower() for value in values if value)
    return query.lower() in haystack


def entity_target_type(section: str) -> str:
    return "CHANNEL" if section == "Channels" else "GROUP"


async def load_recent_activity(app: FastAPI, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, limit)
    lines: list[str] = []
    for actor_user_id, action_key, target_type, target_id, details, created_at in rows:
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        target = f"{target_type}:{target_id}" if target_type and target_id else (target_type or "-")
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | {target} | actor={actor_user_id or '-'}{suffix}")
    return lines


def build_csv_content(columns: list[str], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    return buffer.getvalue()


async def build_export_payload(app: FastAPI, export_key: str, media_only_sentinel: str) -> tuple[str | None, str | None]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if export_key in {"daily", "weekly", "ops"}:
        bundle = await app.state.report_service.build_reports()
        if export_key == "daily":
            return bundle.daily_text, f"everithing_manager_daily_{stamp}.txt"
        if export_key == "weekly":
            return bundle.weekly_text, f"everithing_manager_weekly_{stamp}.txt"
        return bundle.export_text, f"everithing_manager_export_{stamp}.txt"

    if export_key == "schedule-history":
        rows = await load_schedule_history_rows(app, matches_filters, media_only_sentinel)
        lines = ["Schedule History Export", ""]
        for item in rows:
            lines.append(
                f"{item['scheduled_for']} | {item['status']} | {item['channel']} | {item['identifier']} | {item['preview']}"
            )
        if len(lines) == 2:
            lines.append("No schedule history found.")
        return "\n".join(lines), f"everithing_manager_schedule_history_{stamp}.txt"

    if export_key == "channels-csv":
        rows = await load_entity_rows(app, "Channels")
        return build_csv_content(
            ["id", "section", "title", "identifier", "status", "created_at"],
            rows,
        ), f"everithing_manager_channels_{stamp}.csv"

    if export_key == "groups-csv":
        rows = await load_entity_rows(app, "Groups")
        return build_csv_content(
            ["id", "section", "title", "identifier", "status", "created_at"],
            rows,
        ), f"everithing_manager_groups_{stamp}.csv"

    if export_key == "bots-csv":
        rows = await load_bot_rows(app)
        return build_csv_content(
            ["id", "label", "username", "status", "health_url", "action_url", "last_checked"],
            rows,
        ), f"everithing_manager_bots_{stamp}.csv"

    if export_key == "schedules-csv":
        rows = await load_schedule_rows(app, matches_filters, media_only_sentinel)
        return build_csv_content(
            ["id", "channel", "identifier", "status", "scheduled_for", "preview"],
            rows,
        ), f"everithing_manager_schedules_{stamp}.csv"

    if export_key == "schedule-history-csv":
        rows = await load_schedule_history_rows(app, matches_filters, media_only_sentinel)
        return build_csv_content(
            ["id", "channel", "identifier", "status", "scheduled_for", "preview"],
            rows,
        ), f"everithing_manager_schedule_history_{stamp}.csv"

    return None, None


async def load_alert_lines(app: FastAPI, rules: list) -> list[str]:
    alerts: list[str] = []

    pending_channels = await app.state.entity_service.list_channels_by_status("PENDING")
    pending_groups = await app.state.entity_service.list_groups_by_status("PENDING")
    if pending_channels or pending_groups:
        alerts.append(
            f"Pending review: {len(pending_channels)} channel(s), {len(pending_groups)} group(s)."
        )

    failed_schedules = await app.state.schedule_service.list_failed()
    if failed_schedules:
        alerts.append(f"Failed schedules: {len(failed_schedules)} item(s) need retry or review.")

    paused_schedules = await app.state.schedule_service.list_paused()
    recurring_paused = [item for item in paused_schedules if item.recurrence_key]
    if recurring_paused:
        alerts.append(f"Paused recurring schedules: {len(recurring_paused)} item(s).")

    bots = await app.state.bot_service.list_bots()
    degraded_bots = [item for item in bots if item.status in {"OFFLINE", "DEGRADED", "UNKNOWN"}]
    if degraded_bots:
        labels = ", ".join((item.display_name or item.bot_username) for item in degraded_bots[:3])
        suffix = "..." if len(degraded_bots) > 3 else ""
        alerts.append(f"Bot health: {len(degraded_bots)} issue(s) detected -> {labels}{suffix}")

    paused_rules = [item for item in rules if item.status == "PAUSED"]
    if paused_rules:
        labels = ", ".join(item.template_name for item in paused_rules[:3])
        suffix = "..." if len(paused_rules) > 3 else ""
        alerts.append(f"Paused automations: {len(paused_rules)} rule(s) -> {labels}{suffix}")

    no_next_run = [item for item in rules if item.status == "ACTIVE" and not item.next_run_at]
    if no_next_run:
        alerts.append(f"Automation scheduling: {len(no_next_run)} active rule(s) have no next run.")

    return alerts


async def load_delivery_results(app: FastAPI, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, 120)
    interesting = {
        "WEB_BROADCAST_ALL",
        "WEB_BROADCAST_SELECTED",
        "WEB_SCHEDULE_CREATE",
        "WEB_BROADCAST_CHANNEL_MESSAGE",
    }
    lines: list[str] = []
    for actor_user_id, action_key, target_type, target_id, details, created_at in rows:
        if action_key not in interesting:
            continue
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        target_label = f"{target_type}:{target_id}" if target_type and target_id else "-"
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | actor={actor_user_id or '-'} | {target_label}{suffix}")
        if len(lines) >= limit:
            break
    return lines


async def load_recent_automation_activity(app: FastAPI, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, 60)
    lines: list[str] = []
    for actor_user_id, action_key, target_type, target_id, details, created_at in rows:
        if target_type != "AUTOMATION" and not action_key.startswith("AUTOMATION_"):
            continue
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | rule={target_id or '-'} | actor={actor_user_id or '-'}{suffix}")
        if len(lines) >= limit:
            break
    return lines


async def load_automation_insights(app: FastAPI, rules: list) -> list[str]:
    active = [item for item in rules if item.status == "ACTIVE"]
    paused = [item for item in rules if item.status == "PAUSED"]
    custom_owner = 0
    custom_condition = 0
    template_rules = 0

    for item in rules:
        config_json = getattr(item, "config_json", None)
        if not config_json:
            template_rules += 1
            continue
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError:
            template_rules += 1
            continue
        kind = str(config.get("kind", "")).strip().upper() if isinstance(config, dict) else ""
        if kind == "CUSTOM_OWNER_ALERT":
            custom_owner += 1
        elif kind == "CUSTOM_CONDITION_ALERT":
            custom_condition += 1
        else:
            template_rules += 1

    deferred_count = 0
    run_now_count = 0
    condition_match_count = 0
    if app.state.context.oracle_client:
        rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, 160)
        for _, action_key, target_type, _, _, _ in rows:
            if target_type != "AUTOMATION" and not action_key.startswith("AUTOMATION_"):
                continue
            if action_key == "AUTOMATION_RUN_DEFERRED":
                deferred_count += 1
            elif action_key == "AUTOMATION_RULE_RUN_NOW":
                run_now_count += 1
            elif action_key == "AUTOMATION_CONDITION_MATCH":
                condition_match_count += 1

    next_due = sorted(
        [item for item in active if item.next_run_at],
        key=lambda item: item.next_run_at,
    )[:3]
    due_summary = ", ".join(
        f"{item.template_name} @ {item.next_run_at.strftime('%Y-%m-%d %H:%M')}"
        for item in next_due
    ) or "No scheduled next-run entries."

    return [
        f"Total rules: {len(rules)} | Active: {len(active)} | Paused: {len(paused)}",
        f"Custom owner alerts: {custom_owner} | Conditional alerts: {custom_condition} | Template rules: {template_rules}",
        f"Recent deferred runs: {deferred_count} | Manual run-now: {run_now_count} | Condition matches: {condition_match_count}",
        f"Next due: {due_summary}",
    ]


async def load_ops_snapshot(app: FastAPI, rules: list) -> list[str]:
    pending_channels = await app.state.entity_service.list_channels_by_status("PENDING")
    pending_groups = await app.state.entity_service.list_groups_by_status("PENDING")
    failed_schedules = await app.state.schedule_service.list_failed()
    paused_schedules = await app.state.schedule_service.list_paused()
    recurring_paused = [item for item in paused_schedules if item.recurrence_key]
    bots = await app.state.bot_service.list_bots()
    offline_bots = [item for item in bots if item.status == "OFFLINE"]
    degraded_bots = [item for item in bots if item.status in {"DEGRADED", "UNKNOWN"}]
    active_rules = [item for item in rules if item.status == "ACTIVE"]
    paused_rules = [item for item in rules if item.status == "PAUSED"]
    no_next_run = [item for item in active_rules if not item.next_run_at]

    priorities: list[str] = []
    if failed_schedules:
        priorities.append(f"Failed schedules need review: {len(failed_schedules)}")
    if pending_channels or pending_groups:
        priorities.append(
            f"Pending review backlog: {len(pending_channels)} channels, {len(pending_groups)} groups"
        )
    if offline_bots:
        priorities.append(f"Offline bots: {len(offline_bots)}")
    if recurring_paused:
        priorities.append(f"Paused recurring schedules: {len(recurring_paused)}")
    if paused_rules:
        priorities.append(f"Paused automation rules: {len(paused_rules)}")
    if no_next_run:
        priorities.append(f"Active rules without next run: {len(no_next_run)}")

    health_signals: list[str] = []
    if not failed_schedules:
        health_signals.append("No failed schedules right now")
    if not offline_bots and not degraded_bots:
        health_signals.append("Managed bot health looks stable")
    if not pending_channels and not pending_groups:
        health_signals.append("No pending review backlog")
    if not paused_rules:
        health_signals.append("All automation rules currently active or intentionally absent")

    next_due = sorted(
        [item for item in active_rules if item.next_run_at],
        key=lambda item: item.next_run_at,
    )[:3]
    next_due_summary = ", ".join(
        f"{item.template_name} @ {item.next_run_at.strftime('%m-%d %H:%M')}"
        for item in next_due
    ) or "No upcoming automation runs scheduled."

    lines = [
        f"Pressure points: {', '.join(priorities) if priorities else 'None'}",
        f"Healthy signals: {', '.join(health_signals) if health_signals else 'Needs attention'}",
        f"Bot health mix: online={len([item for item in bots if item.status == 'ONLINE'])}, offline={len(offline_bots)}, degraded={len(degraded_bots)}",
        f"Automation mix: active={len(active_rules)}, paused={len(paused_rules)}, next due={next_due_summary}",
    ]
    return lines


async def load_action_center_links(app: FastAPI, rules: list) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    pending_channels = await app.state.entity_service.list_channels_by_status("PENDING")
    pending_groups = await app.state.entity_service.list_groups_by_status("PENDING")
    failed_schedules = await app.state.schedule_service.list_failed()
    paused_schedules = await app.state.schedule_service.list_paused()
    recurring_paused = [item for item in paused_schedules if item.recurrence_key]
    bots = await app.state.bot_service.list_bots()
    offline_bots = [item for item in bots if item.status == "OFFLINE"]
    degraded_bots = [item for item in bots if item.status in {"DEGRADED", "UNKNOWN"}]
    paused_rules = [item for item in rules if item.status == "PAUSED"]

    if failed_schedules:
        links.append(
            {
                "label": f"Review failed schedules ({len(failed_schedules)})",
                "href": "/dashboard?status=FAILED#scheduled-posts",
                "kind": "danger",
            }
        )
    if pending_channels or pending_groups:
        links.append(
            {
                "label": f"Open pending review ({len(pending_channels) + len(pending_groups)})",
                "href": "/dashboard?status=PENDING#managed-channels",
                "kind": "warning",
            }
        )
    if recurring_paused:
        links.append(
            {
                "label": f"Check paused recurring schedules ({len(recurring_paused)})",
                "href": "/dashboard?status=PAUSED#scheduled-posts",
                "kind": "warning",
            }
        )
    if offline_bots:
        first_bot = offline_bots[0]
        links.append(
            {
                "label": f"Inspect offline bot: {first_bot.display_name or first_bot.bot_username}",
                "href": f"/dashboard/bot/{first_bot.id}",
                "kind": "danger",
            }
        )
    elif degraded_bots:
        first_bot = degraded_bots[0]
        links.append(
            {
                "label": f"Inspect degraded bot: {first_bot.display_name or first_bot.bot_username}",
                "href": f"/dashboard/bot/{first_bot.id}",
                "kind": "warning",
            }
        )
    if paused_rules:
        first_rule = paused_rules[0]
        links.append(
            {
                "label": f"Review paused automation: {first_rule.template_name}",
                "href": "/dashboard#automation-rules",
                "kind": "neutral",
            }
        )

    if not links:
        links.append(
            {
                "label": "No urgent actions right now",
                "href": "/dashboard",
                "kind": "safe",
            }
        )
    return links[:6]


async def load_bot_action_history(app: FastAPI, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, 120)
    interesting = {
        "TRIGGER_MANAGED_BOT_ACTION",
        "WEB_TRIGGER_MANAGED_BOT_ACTION",
        "REFRESH_MANAGED_BOT_STATUS",
        "WEB_REFRESH_MANAGED_BOT_STATUS",
        "WEB_REFRESH_ALL_MANAGED_BOT_STATUSES",
    }
    lines: list[str] = []
    for actor_user_id, action_key, target_type, target_id, details, created_at in rows:
        if action_key not in interesting:
            continue
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | bot={target_id or '-'} | actor={actor_user_id or '-'}{suffix}")
        if len(lines) >= limit:
            break
    return lines


async def load_automation_rule_history(app: FastAPI, rules: list, limit_per_rule: int = 3) -> dict[str, list[str]]:
    if not app.state.context.oracle_client or not rules:
        return {}
    rows = await asyncio.to_thread(AuditRepository(app.state.context.oracle_client).list_recent, 120)
    history: dict[str, list[str]] = {str(item.id): [] for item in rules if item.id}
    for actor_user_id, action_key, target_type, target_id, details, created_at in rows:
        if target_type != "AUTOMATION" or not target_id or target_id not in history:
            continue
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        history[target_id].append(f"{stamp} | {action_key} | actor={actor_user_id or '-'}{suffix}")
    return {
        rule_id: lines[:limit_per_rule]
        for rule_id, lines in history.items()
    }


async def load_entity_detail_activity(app: FastAPI, section: str, entity_id: int, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    target_type = entity_target_type(section)
    rows = await asyncio.to_thread(
        AuditRepository(app.state.context.oracle_client).list_recent_for_target,
        target_type,
        str(entity_id),
        limit,
    )
    lines: list[str] = []
    for actor_user_id, action_key, _, _, details, created_at in rows:
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | actor={actor_user_id or '-'}{suffix}")
    return lines


async def load_bot_detail_activity(app: FastAPI, bot_username: str, limit: int = 10) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(
        AuditRepository(app.state.context.oracle_client).list_recent_for_target,
        "BOT",
        bot_username,
        limit,
    )
    lines: list[str] = []
    for actor_user_id, action_key, _, _, details, created_at in rows:
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        lines.append(f"{stamp} | {action_key} | actor={actor_user_id or '-'}{suffix}")
    return lines


def _parse_bot_action_result(details: str | None) -> tuple[str, str, str]:
    if not details:
        return "-", "-", "-"
    if "|body=" not in details:
        return details, "-", "-"

    head, body = details.split("|body=", maxsplit=1)
    parts = head.split(":")
    if len(parts) >= 3:
        result = parts[0]
        method = parts[1]
        status = ":".join(parts[2:])
        return result, method, f"{status} | body={body}"
    return head, "-", f"body={body}"


async def load_bot_action_diagnostics(app: FastAPI, bot_username: str, limit: int = 8) -> list[str]:
    if not app.state.context.oracle_client:
        return []
    rows = await asyncio.to_thread(
        AuditRepository(app.state.context.oracle_client).list_recent_for_target,
        "BOT",
        bot_username,
        40,
    )
    interesting = {
        "TRIGGER_MANAGED_BOT_ACTION",
        "WEB_TRIGGER_MANAGED_BOT_ACTION",
        "WEB_TEST_MANAGED_BOT_ACTION",
        "REFRESH_MANAGED_BOT_STATUS",
        "WEB_REFRESH_MANAGED_BOT_STATUS",
    }
    lines: list[str] = []
    for actor_user_id, action_key, _, _, details, created_at in rows:
        if action_key not in interesting:
            continue
        stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        if "REFRESH" in action_key:
            lines.append(
                f"{stamp} | {action_key} | actor={actor_user_id or '-'} | status={details or '-'}"
            )
        else:
            result, method, summary = _parse_bot_action_result(details)
            lines.append(
                f"{stamp} | {action_key} | actor={actor_user_id or '-'} | {result} | {method} | {summary}"
            )
        if len(lines) >= limit:
            break
    return lines


async def record_audit_event(
    app: FastAPI,
    actor_user_id: int | None,
    action_key: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: str | None = None,
) -> None:
    if not app.state.context.oracle_client:
        return
    await asyncio.to_thread(
        AuditRepository(app.state.context.oracle_client).insert,
        AuditLogRecord(
            actor_user_id=actor_user_id,
            action_key=action_key,
            target_type=target_type,
            target_id=target_id,
            details=details,
        ),
    )


async def load_dashboard_stats(app: FastAPI) -> dict[str, int]:
    active_channels = await app.state.entity_service.list_channels()
    active_groups = await app.state.entity_service.list_groups()
    pending_channels = await app.state.entity_service.list_channels_by_status("PENDING")
    pending_groups = await app.state.entity_service.list_groups_by_status("PENDING")
    pending_schedules = await app.state.schedule_service.list_pending()
    failed_schedules = await app.state.schedule_service.list_failed()
    rules = await app.state.automation_service.list_rules()
    active_rules = [item for item in rules if item.status == "ACTIVE"]
    bots = await app.state.bot_service.list_bots()
    online_bots = [item for item in bots if item.status == "ONLINE"]
    return {
        "active_channels": len(active_channels),
        "active_groups": len(active_groups),
        "pending_channels": len(pending_channels),
        "pending_groups": len(pending_groups),
        "pending_schedules": len(pending_schedules),
        "failed_schedules": len(failed_schedules),
        "active_rules": len(active_rules),
        "online_bots": len(online_bots),
    }


async def load_active_channel_options(app: FastAPI) -> list[dict[str, str]]:
    records = await app.state.entity_service.list_channels()
    rows: list[dict[str, str]] = []
    for item in records:
        rows.append(
            {
                "identifier": item.chat_identifier,
                "title": item.title or item.chat_identifier,
            }
        )
    return rows[:100]
