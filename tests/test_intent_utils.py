import unittest

from app.services.intent_utils import parse_natural_intent


class IntentUtilsTests(unittest.TestCase):
    def test_parse_direct_section_intents(self) -> None:
        self.assertEqual(parse_natural_intent("home"), ("section", "Home"))
        self.assertEqual(parse_natural_intent("bots"), ("section", "Bots"))

    def test_parse_flow_intents(self) -> None:
        self.assertEqual(parse_natural_intent("post"), ("flow", "post"))
        self.assertEqual(parse_natural_intent("quick schedule"), ("flow", "schedule"))
        self.assertEqual(parse_natural_intent("send broadcast"), ("flow", "broadcast"))
        self.assertEqual(parse_natural_intent("review pending"), ("flow", "review"))
        self.assertEqual(parse_natural_intent("alerts"), ("flow", "alerts"))

    def test_parse_fuzzy_intents(self) -> None:
        self.assertEqual(parse_natural_intent("please review pending"), ("flow", "review"))
        self.assertEqual(parse_natural_intent("quick post now"), ("flow", "post"))
        self.assertIsNone(parse_natural_intent("hello there"))


if __name__ == "__main__":
    unittest.main()
