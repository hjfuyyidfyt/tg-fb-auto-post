from __future__ import annotations

import unittest

from app.web_validation import validate_automation_timing


class WebValidationTests(unittest.TestCase):
    def test_valid_timing_configuration(self) -> None:
        self.assertIsNone(validate_automation_timing(60, 23, 8))

    def test_invalid_cooldown(self) -> None:
        self.assertEqual(
            validate_automation_timing(10081, None, None),
            "Cooldown must be between 0 and 10080 minutes.",
        )

    def test_invalid_quiet_hours_pair(self) -> None:
        self.assertEqual(
            validate_automation_timing(0, 23, None),
            "Set both quiet start and quiet end hours, or leave both blank.",
        )

    def test_invalid_same_quiet_hour(self) -> None:
        self.assertEqual(
            validate_automation_timing(0, 22, 22),
            "Quiet start and quiet end cannot be the same hour.",
        )


if __name__ == "__main__":
    unittest.main()
