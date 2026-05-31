from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.schedule import ScheduledPostRecord


@dataclass(slots=True)
class ParsedScheduleSpec:
    scheduled_for: datetime
    recurrence_key: str | None = None


DASHBOARD_TIMEZONE = ZoneInfo("Asia/Dhaka")


def parse_schedule_time(value: str, timezone: ZoneInfo = DASHBOARD_TIMEZONE) -> ParsedScheduleSpec:
    normalized = (value or "").strip()
    now = datetime.now(timezone)

    shorthand = normalized.lower()
    if shorthand == "d":
        return ParsedScheduleSpec(
            scheduled_for=(now + timedelta(days=1)).replace(tzinfo=None),
            recurrence_key="DAILY",
        )
    if shorthand == "w":
        return ParsedScheduleSpec(
            scheduled_for=(now + timedelta(weeks=1)).replace(tzinfo=None),
            recurrence_key="WEEKLY",
        )
    if shorthand == "m":
        year = now.year + (1 if now.month == 12 else 0)
        month = 1 if now.month == 12 else now.month + 1
        day = min(now.day, calendar.monthrange(year, month)[1])
        return ParsedScheduleSpec(
            scheduled_for=now.replace(year=year, month=month, day=day, tzinfo=None),
            recurrence_key="MONTHLY",
        )

    dhms_match = re.fullmatch(r"(\d+)-(\d+)-(\d+)-(\d+)", normalized)
    if dhms_match:
        days = int(dhms_match.group(1))
        hours = int(dhms_match.group(2))
        minutes = int(dhms_match.group(3))
        seconds = int(dhms_match.group(4))
        return ParsedScheduleSpec(
            scheduled_for=(now + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)).replace(
                tzinfo=None
            )
        )

    relative_match = re.fullmatch(r"(?i)(\d+)\s*([mhd])", normalized)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        delta_map = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
        }
        return ParsedScheduleSpec(scheduled_for=(now + delta_map[unit]).replace(tzinfo=None))

    tomorrow_match = re.fullmatch(r"(?i)tomorrow\s+(\d{1,2}):(\d{2})", normalized)
    if tomorrow_match:
        hour = int(tomorrow_match.group(1))
        minute = int(tomorrow_match.group(2))
        target = now + timedelta(days=1)
        return ParsedScheduleSpec(
            scheduled_for=target.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=None)
        )

    time_only_match = re.fullmatch(r"(\d{1,2}):(\d{2})", normalized)
    if time_only_match:
        hour = int(time_only_match.group(1))
        minute = int(time_only_match.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return ParsedScheduleSpec(scheduled_for=target.replace(tzinfo=None))

    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return ParsedScheduleSpec(scheduled_for=datetime.strptime(normalized, pattern))
        except ValueError:
            continue
    raise ValueError("Invalid schedule time format")


def next_occurrence(record: ScheduledPostRecord) -> datetime | None:
    if not record.recurrence_key or not record.scheduled_for:
        return None

    scheduled = record.scheduled_for
    if record.recurrence_key == "DAILY":
        return scheduled + timedelta(days=1)
    if record.recurrence_key == "WEEKLY":
        return scheduled + timedelta(weeks=1)
    if record.recurrence_key == "MONTHLY":
        year = scheduled.year + (1 if scheduled.month == 12 else 0)
        month = 1 if scheduled.month == 12 else scheduled.month + 1
        day = min(scheduled.day, calendar.monthrange(year, month)[1])
        return scheduled.replace(year=year, month=month, day=day)
    if record.recurrence_key == "WORKDAYS":
        next_day = scheduled + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day
    if record.recurrence_key == "WEEKEND":
        next_day = scheduled + timedelta(days=1)
        while next_day.weekday() < 5:
            next_day += timedelta(days=1)
        return next_day
    return None
