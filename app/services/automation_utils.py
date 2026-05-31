from __future__ import annotations


def normalize_trigger_keys(config: dict[str, object]) -> list[str]:
    raw_list = config.get("trigger_keys")
    if isinstance(raw_list, list):
        values = [
            str(item).strip().upper()
            for item in raw_list
            if str(item).strip()
        ]
        if values:
            return values
    legacy_value = str(config.get("trigger_key", "")).strip().upper()
    if legacy_value:
        return [legacy_value]
    return ["PENDING_REVIEW"]


def summarize_items(items: list[str], limit: int = 5) -> str:
    if not items:
        return "-"
    preview = items[:limit]
    suffix = f" ... (+{len(items) - limit} more)" if len(items) > limit else ""
    return "; ".join(preview) + suffix


def render_condition_message(
    template: str,
    *,
    trigger_key: str,
    count: int,
    threshold: int,
    details: str,
) -> str:
    rendered = template
    replacements = {
        "{{trigger}}": trigger_key,
        "{{count}}": str(count),
        "{{threshold}}": str(threshold),
        "{{details}}": details,
    }
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def safe_hour(value: object) -> int | None:
    try:
        hour = int(value)
    except (TypeError, ValueError):
        return None
    return hour if 0 <= hour <= 23 else None


def should_run_custom_rule(
    *,
    last_run_at: datetime | None,
    config: dict[str, object],
    now_utc: datetime,
    dhaka_now: datetime,
) -> tuple[bool, datetime | None]:
    cooldown_minutes = max(0, int(config.get("cooldown_minutes", 0) or 0))
    if cooldown_minutes > 0 and last_run_at:
        next_allowed = last_run_at + timedelta(minutes=cooldown_minutes)
        if next_allowed > now_utc:
            return False, next_allowed

    quiet_start = safe_hour(config.get("quiet_hours_start"))
    quiet_end = safe_hour(config.get("quiet_hours_end"))
    if quiet_start is not None and quiet_end is not None and quiet_start != quiet_end:
        current_hour = dhaka_now.hour
        in_quiet_hours = (
            quiet_start <= current_hour < quiet_end
            if quiet_start < quiet_end
            else current_hour >= quiet_start or current_hour < quiet_end
        )
        if in_quiet_hours:
            defer_local = dhaka_now.replace(minute=0, second=0, microsecond=0)
            while True:
                defer_local += timedelta(hours=1)
                hour = defer_local.hour
                still_quiet = (
                    quiet_start <= hour < quiet_end
                    if quiet_start < quiet_end
                    else hour >= quiet_start or hour < quiet_end
                )
                if not still_quiet:
                    return False, defer_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return True, None
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
