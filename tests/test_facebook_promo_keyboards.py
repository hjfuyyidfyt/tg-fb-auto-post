import unittest

try:
    from app.keyboards.section_actions import (
        build_facebook_promo_access_v2_keyboard,
        build_facebook_promo_ai_hub_v3_keyboard,
        build_facebook_promo_publish_confirm_keyboard,
        build_facebook_promo_ready_campaign_detail_keyboard,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - local lightweight env may omit aiogram
    if exc.name != "aiogram":
        raise
    build_facebook_promo_access_v2_keyboard = None
    build_facebook_promo_ai_hub_v3_keyboard = None
    build_facebook_promo_publish_confirm_keyboard = None
    build_facebook_promo_ready_campaign_detail_keyboard = None


class FacebookPromoKeyboardTests(unittest.TestCase):
    @unittest.skipIf(build_facebook_promo_access_v2_keyboard is None, "aiogram is not installed")
    def test_access_keyboard_includes_setup_help(self) -> None:
        keyboard = build_facebook_promo_access_v2_keyboard(True, True)
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertIn("fbpromo:accesshelp", callbacks)

    @unittest.skipIf(build_facebook_promo_ai_hub_v3_keyboard is None, "aiogram is not installed")
    def test_hub_keyboard_includes_guide_and_image_safety(self) -> None:
        keyboard = build_facebook_promo_ai_hub_v3_keyboard(
            has_access=True,
            is_active=False,
            has_notes=True,
            has_plan=True,
            has_campaigns=True,
            has_ready_queue=True,
        )
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertIn("fbpromo:guide", callbacks)
        self.assertIn("fbpromo:image:status", callbacks)

    @unittest.skipIf(build_facebook_promo_ready_campaign_detail_keyboard is None, "aiogram is not installed")
    def test_ready_campaign_publish_now_opens_confirmation_step(self) -> None:
        keyboard = build_facebook_promo_ready_campaign_detail_keyboard(3)
        first_row = keyboard.inline_keyboard[0]

        self.assertEqual(first_row[1].text, "Publish Now")
        self.assertEqual(first_row[1].callback_data, "fbpromo:publishnow:3")

    @unittest.skipIf(build_facebook_promo_publish_confirm_keyboard is None, "aiogram is not installed")
    def test_publish_confirm_keyboard_uses_separate_live_callback(self) -> None:
        keyboard = build_facebook_promo_publish_confirm_keyboard(3)

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "Confirm Live Publish")
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "fbpromo:publishconfirm:3")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "fbpromo:publishdry:3")
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, "fbpromo:campaign:3")


if __name__ == "__main__":
    unittest.main()
