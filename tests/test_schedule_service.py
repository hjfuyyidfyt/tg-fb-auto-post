from __future__ import annotations

import unittest
from datetime import datetime

from app.models.schedule import ScheduledPostRecord
from app.services.schedule_utils import DASHBOARD_TIMEZONE, next_occurrence, parse_schedule_time


class ScheduleServiceTests(unittest.TestCase):
    def test_parse_one_time_absolute(self) -> None:
        parsed = parse_schedule_time("2026-04-20 23:30")
        self.assertEqual(parsed.scheduled_for, datetime(2026, 4, 20, 23, 30))
        self.assertIsNone(parsed.recurrence_key)

    def test_parse_daily_weekly_monthly_recurrence(self) -> None:
        self.assertEqual(parse_schedule_time("d").recurrence_key, "DAILY")
        self.assertEqual(parse_schedule_time("w").recurrence_key, "WEEKLY")
        self.assertEqual(parse_schedule_time("m").recurrence_key, "MONTHLY")

    def test_parse_relative_dhms(self) -> None:
        parsed = parse_schedule_time("0-00-00-30", DASHBOARD_TIMEZONE)
        delta = parsed.scheduled_for - datetime.now(DASHBOARD_TIMEZONE).replace(tzinfo=None)
        self.assertTrue(20 <= delta.total_seconds() <= 40)
        self.assertIsNone(parsed.recurrence_key)

    def test_next_occurrence_daily(self) -> None:
        record = ScheduledPostRecord(
            id=1,
            channel_identifier="@demo",
            channel_title="Demo",
            message_text="hello",
            scheduled_for=datetime(2026, 4, 20, 10, 0),
            recurrence_key="DAILY",
            media_path=None,
            media_name=None,
            media_type=None,
            status="PENDING",
            created_by_user_id=1,
        )
        self.assertEqual(
            next_occurrence(record),
            datetime(2026, 4, 21, 10, 0),
        )

    def test_next_occurrence_monthly_handles_end_of_month(self) -> None:
        record = ScheduledPostRecord(
            id=2,
            channel_identifier="@demo",
            channel_title="Demo",
            message_text="hello",
            scheduled_for=datetime(2026, 1, 31, 10, 0),
            recurrence_key="MONTHLY",
            media_path=None,
            media_name=None,
            media_type=None,
            status="PENDING",
            created_by_user_id=1,
        )
        self.assertEqual(
            next_occurrence(record),
            datetime(2026, 2, 28, 10, 0),
        )

    def test_next_occurrence_unknown_recurrence_returns_none(self) -> None:
        record = ScheduledPostRecord(
            id=3,
            channel_identifier="@demo",
            channel_title="Demo",
            message_text="hello",
            scheduled_for=datetime(2026, 4, 20, 10, 0),
            recurrence_key="UNKNOWN",
            media_path=None,
            media_name=None,
            media_type=None,
            status="PENDING",
            created_by_user_id=1,
        )
        self.assertIsNone(next_occurrence(record))

    def test_next_occurrence_workdays_skips_weekend(self) -> None:
        record = ScheduledPostRecord(
            id=4,
            channel_identifier="@demo",
            channel_title="Demo",
            message_text="hello",
            scheduled_for=datetime(2026, 4, 24, 10, 0),
            recurrence_key="WORKDAYS",
            media_path=None,
            media_name=None,
            media_type=None,
            status="PENDING",
            created_by_user_id=1,
        )
        self.assertEqual(
            next_occurrence(record),
            datetime(2026, 4, 27, 10, 0),
        )

    def test_next_occurrence_weekend_skips_weekdays(self) -> None:
        record = ScheduledPostRecord(
            id=5,
            channel_identifier="@demo",
            channel_title="Demo",
            message_text="hello",
            scheduled_for=datetime(2026, 4, 26, 10, 0),
            recurrence_key="WEEKEND",
            media_path=None,
            media_name=None,
            media_type=None,
            status="PENDING",
            created_by_user_id=1,
        )
        self.assertEqual(
            next_occurrence(record),
            datetime(2026, 5, 2, 10, 0),
        )


if __name__ == "__main__":
    unittest.main()
