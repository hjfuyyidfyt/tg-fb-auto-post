import unittest

from app.services.intent_utils import build_intent_fallback_text


class IntentFallbackTests(unittest.TestCase):
    def test_build_intent_fallback_text_with_input(self) -> None:
        text = build_intent_fallback_text("hello")
        self.assertIn("hello", text)
        self.assertIn("post", text)
        self.assertIn("schedule", text)

    def test_build_intent_fallback_text_without_input(self) -> None:
        text = build_intent_fallback_text("")
        self.assertIn("broadcast", text)
        self.assertIn("menu buttons", text)


if __name__ == "__main__":
    unittest.main()
