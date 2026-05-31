from __future__ import annotations

import unittest

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.automation_utils import (
    normalize_trigger_keys,
    render_condition_message,
    safe_hour,
    should_run_custom_rule,
    summarize_items,
)


class AutomationUtilsTests(unittest.TestCase):
    def test_normalize_trigger_keys_prefers_list(self) -> None:
        self.assertEqual(
            normalize_trigger_keys({"trigger_keys": ["pending_review", "offline_bots"]}),
            ["PENDING_REVIEW", "OFFLINE_BOTS"],
        )

    def test_normalize_trigger_keys_falls_back_to_legacy_key(self) -> None:
        self.assertEqual(
            normalize_trigger_keys({"trigger_key": "failed_schedules"}),
            ["FAILED_SCHEDULES"],
        )

    def test_render_condition_message(self) -> None:
        rendered = render_condition_message(
            "Alert {{trigger}} count={{count}} threshold={{threshold}} details={{details}}",
            trigger_key="OFFLINE_BOTS",
            count=3,
            threshold=2,
            details="bot-a; bot-b",
        )
        self.assertEqual(
            rendered,
            "Alert OFFLINE_BOTS count=3 threshold=2 details=bot-a; bot-b",
        )

    def test_summarize_items_adds_suffix(self) -> None:
        self.assertEqual(
            summarize_items(["a", "b", "c"], limit=2),
            "a; b ... (+1 more)",
        )

    def test_safe_hour(self) -> None:
        self.assertEqual(safe_hour("23"), 23)
        self.assertIsNone(safe_hour("99"))

    def test_should_run_custom_rule_cooldown_defers(self) -> None:
        should_run, defer_until = should_run_custom_rule(
            last_run_at=datetime(2026, 4, 20, 10, 0),
            config={"cooldown_minutes": 120},
            now_utc=datetime(2026, 4, 20, 11, 0),
            dhaka_now=datetime(2026, 4, 20, 17, 0, tzinfo=ZoneInfo("Asia/Dhaka")),
        )
        self.assertFalse(should_run)
        self.assertEqual(defer_until, datetime(2026, 4, 20, 12, 0))

    def test_should_run_custom_rule_quiet_hours_defers_overnight(self) -> None:
        should_run, defer_until = should_run_custom_rule(
            last_run_at=None,
            config={"quiet_hours_start": 23, "quiet_hours_end": 8},
            now_utc=datetime(2026, 4, 20, 18, 30),
            dhaka_now=datetime(2026, 4, 21, 0, 30, tzinfo=ZoneInfo("Asia/Dhaka")),
        )
        self.assertFalse(should_run)
        self.assertEqual(defer_until, datetime(2026, 4, 21, 2, 0))

    def test_should_run_custom_rule_allows_outside_quiet_hours(self) -> None:
        should_run, defer_until = should_run_custom_rule(
            last_run_at=None,
            config={"quiet_hours_start": 23, "quiet_hours_end": 8},
            now_utc=datetime(2026, 4, 20, 5, 0),
            dhaka_now=datetime(2026, 4, 20, 11, 0, tzinfo=ZoneInfo("Asia/Dhaka")),
        )
        self.assertTrue(should_run)
        self.assertIsNone(defer_until)


if __name__ == "__main__":
    unittest.main()
