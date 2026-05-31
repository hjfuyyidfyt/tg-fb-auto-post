from __future__ import annotations

import unittest

from app.services.bot_action_utils import (
    normalize_action_presets_json,
    parse_action_presets,
    parse_bot_input,
)


class ManagedBotServiceTests(unittest.TestCase):
    def test_parse_advanced_bot_input(self) -> None:
        parsed = parse_bot_input(
            "@demo_bot | Demo Bot | https://health | https://action | POST | "
            '{"event":"deploy","bot":"{{bot_username}}"} | X-Auth | secret123 | notes'
        )
        self.assertEqual(parsed[0], "@demo_bot")
        self.assertEqual(parsed[1], "Demo Bot")
        self.assertEqual(parsed[4], "POST")
        self.assertEqual(parsed[6], "X-Auth")
        self.assertEqual(parsed[7], "secret123")
        self.assertEqual(parsed[8], "notes")

    def test_normalize_action_presets_json(self) -> None:
        normalized = normalize_action_presets_json(
            '[{"label":"Restart","method":"post","payload":"{\\"event\\":\\"restart\\"}"}]'
        )
        self.assertIsNotNone(normalized)
        presets = parse_action_presets(normalized)
        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0].label, "Restart")
        self.assertEqual(presets[0].method, "POST")

    def test_invalid_presets_return_none(self) -> None:
        self.assertIsNone(normalize_action_presets_json('{"bad":"shape"}'))


if __name__ == "__main__":
    unittest.main()
