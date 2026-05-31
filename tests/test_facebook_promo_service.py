import unittest
import asyncio
import json
from dataclasses import asdict

from app.services.facebook_promo_ai import (
    AlibabaImageAdapter,
    AlibabaImageResult,
    FacebookGraphAdapter,
    FacebookGraphResponse,
    FacebookPromoAIService,
    FacebookPromoProfile,
    GeneratedPromoImage,
    PendingFacebookPromoAction,
    PromoDraft,
    SavedPromoCampaign,
)


class FacebookPromoAIServiceTests(unittest.TestCase):
    def test_is_ready_requires_access_and_notes(self) -> None:
        profile = FacebookPromoProfile(telegram_user_id=1)
        self.assertFalse(FacebookPromoAIService.is_ready(profile))

        profile.page_id = "123"
        profile.page_access_token = "token"
        profile.brand_notes = "Women's fashion page"
        self.assertTrue(FacebookPromoAIService.is_ready(profile))

    def test_mask_token_short_and_long(self) -> None:
        self.assertEqual(FacebookPromoAIService.mask_token(None), "Not connected")
        self.assertEqual(FacebookPromoAIService.mask_token("123456789"), "Saved")
        self.assertEqual(FacebookPromoAIService.mask_token("1234567890abcdef"), "1234...cdef")

    def test_normalize_page_id_accepts_common_facebook_urls(self) -> None:
        self.assertEqual(FacebookPromoAIService.normalize_page_id("123456"), "123456")
        self.assertEqual(FacebookPromoAIService.normalize_page_id("https://www.facebook.com/myshop/"), "myshop")
        self.assertEqual(
            FacebookPromoAIService.normalize_page_id("https://facebook.com/pages/My-Shop/987654321"),
            "987654321",
        )

    def test_access_readiness_reports_missing_and_short_token(self) -> None:
        empty_status = FacebookPromoAIService.build_access_readiness(FacebookPromoProfile(telegram_user_id=1))
        self.assertFalse(empty_status.ready)
        self.assertIn("Page ID is missing.", empty_status.issues)
        self.assertIn("Page access token is missing.", empty_status.issues)

        short_token_status = FacebookPromoAIService.build_access_readiness(
            FacebookPromoProfile(telegram_user_id=1, page_id="123", page_access_token="short")
        )
        self.assertFalse(short_token_status.ready)
        self.assertIn("too short", short_token_status.issues[0])

        ready_status = FacebookPromoAIService.build_access_readiness(
            FacebookPromoProfile(telegram_user_id=1, page_id="123", page_access_token="EAA" + "x" * 40)
        )
        self.assertTrue(ready_status.ready)
        self.assertEqual(ready_status.issues, [])

    def test_merge_task_into_strategy_without_storage(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService()
            await service.start_new_task(1)
            pending = await service.get_pending_action(1)
            self.assertIsNone(pending)

            profile = FacebookPromoProfile(
                telegram_user_id=1,
                page_id="123",
                page_access_token="token",
                brand_notes="fashion",
            )
            merged = await service.save_profile(profile)
            self.assertEqual(merged.brand_notes, "fashion")

        asyncio.run(run())

    def test_generate_recommendations_for_sale(self) -> None:
        pending = PendingFacebookPromoAction(
            stage="await_angle",
            goal_key="SALE",
            goal_label="Product Sale",
            topic="Ladies bag",
            audience="Women 20-35",
            image_mode="NEEDED",
        )
        recommendations = FacebookPromoAIService.generate_recommendations(pending)
        self.assertEqual(len(recommendations), 3)
        self.assertEqual(recommendations[0].key, "PREMIUM_VALUE")

    def test_generate_strategy_plan_uses_selected_angle(self) -> None:
        pending = PendingFacebookPromoAction(
            stage="await_plan_review",
            goal_key="SALE",
            goal_label="Product Sale",
            topic="Ladies bag",
            audience="Women 20-35",
            image_mode="NEEDED",
            selected_angle="PREMIUM_VALUE",
        )
        plan = FacebookPromoAIService.generate_strategy_plan(pending)
        self.assertIn("premium", plan.positioning.lower())
        self.assertEqual(plan.angle_title, "Premium value angle")

    def test_generate_draft_from_saved_strategy(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            strategy_notes=(
                "Goal: Product Sale\n"
                "Topic: Ladies bag\n"
                "Audience: Women 20-35\n"
                "Image mode: NEEDED"
            ),
        )
        pending = PendingFacebookPromoAction(
            stage="await_plan_review",
            goal_key="SALE",
            goal_label="Product Sale",
            topic="Ladies bag",
            audience="Women 20-35",
            image_mode="NEEDED",
            selected_angle="PREMIUM_VALUE",
        )
        plan = FacebookPromoAIService.generate_strategy_plan(pending)
        draft = FacebookPromoAIService.generate_draft(profile, plan)
        self.assertIn("Ladies bag", draft.headline)
        self.assertIn("premium", draft.primary_copy.lower())
        self.assertIn("#LadiesBag", draft.hashtags)

    def test_refine_draft_shorter_and_premium(self) -> None:
        draft = FacebookPromoAIService.refine_draft(
            FacebookPromoAIService.generate_draft(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    strategy_notes=(
                        "Goal: Product Sale\n"
                        "Topic: Ladies bag\n"
                        "Audience: Women 20-35\n"
                        "Image mode: NEEDED"
                    ),
                ),
                FacebookPromoAIService.generate_strategy_plan(
                    PendingFacebookPromoAction(
                        stage="await_plan_review",
                        goal_key="SALE",
                        goal_label="Product Sale",
                        topic="Ladies bag",
                        audience="Women 20-35",
                        image_mode="NEEDED",
                        selected_angle="PREMIUM_VALUE",
                    )
                ),
            ),
            "make it shorter and more premium",
        )
        self.assertTrue(draft.headline.startswith("Premium "))
        self.assertLessEqual(len(draft.primary_copy), 421)

    def test_refine_draft_urgent_strengthens_cta(self) -> None:
        base = FacebookPromoAIService.generate_draft(
            FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
            ),
            FacebookPromoAIService.generate_strategy_plan(
                PendingFacebookPromoAction(
                    stage="await_plan_review",
                    goal_key="SALE",
                    goal_label="Product Sale",
                    topic="Ladies bag",
                    audience="Women 20-35",
                    image_mode="NEEDED",
                    selected_angle="OFFER_PUSH",
                )
            ),
        )
        urgent = FacebookPromoAIService.refine_draft(base, "make it more urgent with stronger CTA")
        self.assertIn("best offer before it ends", urgent.cta.lower())

    def test_refine_draft_minimal_updates_image_concept(self) -> None:
        base = FacebookPromoAIService.generate_draft(
            FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
            ),
            FacebookPromoAIService.generate_strategy_plan(
                PendingFacebookPromoAction(
                    stage="await_plan_review",
                    goal_key="SALE",
                    goal_label="Product Sale",
                    topic="Ladies bag",
                    audience="Women 20-35",
                    image_mode="NEEDED",
                    selected_angle="PREMIUM_VALUE",
                )
            ),
        )
        refined = FacebookPromoAIService.refine_draft(base, "make the image concept minimal")
        self.assertIn("minimal", refined.image_concept.lower())

    def test_generate_draft_applies_saved_preferences(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            strategy_notes=(
                "Goal: Product Sale\n"
                "Topic: Ladies bag\n"
                "Audience: Women 20-35\n"
                "Image mode: NEEDED"
            ),
            preferred_tone="premium",
            preferred_cta_style="inbox",
            preferred_image_style="lifestyle",
        )
        pending = PendingFacebookPromoAction(
            stage="await_plan_review",
            goal_key="SALE",
            goal_label="Product Sale",
            topic="Ladies bag",
            audience="Women 20-35",
            image_mode="NEEDED",
            selected_angle="PREMIUM_VALUE",
        )
        draft = FacebookPromoAIService.generate_draft(
            profile,
            FacebookPromoAIService.generate_strategy_plan(pending),
        )
        self.assertTrue(draft.headline.startswith("Premium "))
        self.assertIn("Inbox now", draft.cta)
        self.assertIn("Lifestyle visual direction", draft.image_concept)

    def test_describe_preferences_returns_defaults(self) -> None:
        profile = FacebookPromoProfile(telegram_user_id=1)
        preferences = FacebookPromoAIService.describe_preferences(profile)
        self.assertEqual(
            preferences,
            {
                "tone": "balanced",
                "emoji": "light",
                "cta": "direct",
                "image": "brand-fit",
            },
        )

    def test_infer_preferences_from_approved_campaign(self) -> None:
        campaigns = [
            SavedPromoCampaign(
                title="Premium Ladies Bag",
                goal="Product Sale",
                topic="Ladies bag",
                created_at="2026-05-20 12:00:00",
                draft_json=json.dumps(
                    {
                        "headline": "Premium Ladies Bag",
                        "primary_copy": "Main copy",
                        "short_copy": "Short copy ✨",
                        "cta": "Inbox now to order, check price, or reserve yours today.",
                        "hashtags": "#LadiesBag #BrandPost",
                        "image_concept": "Lifestyle visual direction. Premium visual direction. Main visual",
                    }
                ),
                status="READY_TO_PUBLISH",
            )
        ]
        learned = FacebookPromoAIService.infer_preferences_from_campaigns(campaigns)
        self.assertEqual(learned["tone"], "premium")
        self.assertEqual(learned["emoji"], "playful")
        self.assertEqual(learned["cta"], "inbox")
        self.assertEqual(learned["image"], "lifestyle")

    def test_describe_preferences_marks_learned_values(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            saved_campaigns_json=json.dumps(
                [
                    asdict(
                        SavedPromoCampaign(
                            title="Premium Ladies Bag",
                            goal="Product Sale",
                            topic="Ladies bag",
                            created_at="2026-05-20 12:00:00",
                            draft_json=json.dumps(
                                {
                                    "headline": "Premium Ladies Bag",
                                    "primary_copy": "Main copy",
                                    "short_copy": "Short copy",
                                    "cta": "Inbox now to order, check price, or reserve yours today.",
                                    "hashtags": "#LadiesBag",
                                    "image_concept": "Premium visual direction. Main visual",
                                }
                            ),
                            status="READY_TO_PUBLISH",
                        )
                    )
                ]
            ),
        )
        preferences = FacebookPromoAIService.describe_preferences(profile)
        self.assertEqual(preferences["tone"], "premium (learned)")
        self.assertEqual(preferences["cta"], "inbox (learned)")

    def test_ready_campaign_index_items_preserves_original_indices(self) -> None:
        campaigns = [
            SavedPromoCampaign("Draft one", "Promo", "Topic A", "2026-05-21", "{}", "DRAFT"),
            SavedPromoCampaign("Ready one", "Promo", "Topic B", "2026-05-21", "{}", "READY_TO_PUBLISH"),
            SavedPromoCampaign("Ready two", "Promo", "Topic C", "2026-05-21", "{}", "READY_TO_PUBLISH"),
        ]
        self.assertEqual(
            FacebookPromoAIService.ready_campaign_index_items(campaigns),
            [(1, "Ready one"), (2, "Ready two")],
        )

    def test_published_campaign_index_items_preserves_original_indices(self) -> None:
        campaigns = [
            SavedPromoCampaign("Draft one", "Promo", "Topic A", "2026-05-21", "{}", "DRAFT"),
            SavedPromoCampaign("Published one", "Promo", "Topic B", "2026-05-21", "{}", "PUBLISHED"),
            SavedPromoCampaign("Ready one", "Promo", "Topic C", "2026-05-21", "{}", "READY_TO_PUBLISH"),
            SavedPromoCampaign("Published two", "Promo", "Topic D", "2026-05-21", "{}", "PUBLISHED"),
        ]
        self.assertEqual(
            FacebookPromoAIService.published_campaign_index_items(campaigns),
            [(1, "Published one"), (3, "Published two")],
        )

    def test_list_published_campaigns_filters_status(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                saved_campaigns_json=json.dumps(
                    [
                        asdict(SavedPromoCampaign("Draft one", "Promo", "Topic A", "2026-05-21", "{}", "DRAFT")),
                        asdict(
                            SavedPromoCampaign(
                                "Published one",
                                "Promo",
                                "Topic B",
                                "2026-05-21",
                                "{}",
                                "PUBLISHED",
                                facebook_post_id="123_456",
                            )
                        ),
                    ]
                ),
            )
            await service.save_profile(profile)
            campaigns = await service.list_published_campaigns(1)
            self.assertEqual(len(campaigns), 1)
            self.assertEqual(campaigns[0].title, "Published one")
            self.assertEqual(campaigns[0].facebook_post_id, "123_456")

        asyncio.run(run())

    def test_build_page_feed_publish_request_shape(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            page_id="123",
            page_access_token="secret-token",
        )
        draft = FacebookPromoAIService.generate_draft(
            FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
            ),
            FacebookPromoAIService.generate_strategy_plan(
                PendingFacebookPromoAction(
                    stage="await_plan_review",
                    goal_key="SALE",
                    goal_label="Product Sale",
                    topic="Ladies bag",
                    audience="Women 20-35",
                    image_mode="NEEDED",
                    selected_angle="PREMIUM_VALUE",
                )
            ),
        )
        request = FacebookPromoAIService.build_page_feed_publish_request(profile, draft)
        self.assertIsNotNone(request)
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.url.endswith("/123/feed"))
        self.assertEqual(request.headers["Authorization"], "Bearer <PAGE_ACCESS_TOKEN>")
        self.assertIn("Ladies bag", request.payload["message"])

    def test_build_page_publish_request_uses_photos_when_image_exists(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            page_id="123",
            page_access_token="secret-token",
        )
        draft = PromoDraft(
            headline="Premium Ladies Bag",
            primary_copy="Main copy",
            short_copy="Short copy",
            cta="Inbox now",
            hashtags="#LadiesBag",
            image_concept="Premium visual",
        )
        image = GeneratedPromoImage(
            model="z-image-turbo",
            prompt="Create product image",
            image_urls=["https://cdn.example.com/promo.png"],
            created_at="2026-05-21 10:00:00",
        )

        request = FacebookPromoAIService.build_page_publish_request(profile, draft, image)

        self.assertIsNotNone(request)
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.url.endswith("/123/photos"))
        self.assertEqual(request.payload["url"], "https://cdn.example.com/promo.png")
        self.assertIn("Premium Ladies Bag", request.payload["caption"])
        self.assertNotIn("message", request.payload)

    def test_build_page_publish_request_rejects_non_public_image_url(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            page_id="123",
            page_access_token="secret-token",
        )
        draft = PromoDraft(
            headline="Premium Ladies Bag",
            primary_copy="Main copy",
            short_copy="Short copy",
            cta="Inbox now",
            hashtags="#LadiesBag",
            image_concept="Premium visual",
        )
        image = GeneratedPromoImage(
            model="z-image-turbo",
            prompt="Create product image",
            image_urls=["http://localhost/promo.png"],
            created_at="2026-05-21 10:00:00",
        )

        self.assertIsNone(FacebookPromoAIService.build_page_publish_request(profile, draft, image))
        self.assertIn(
            "HTTPS",
            FacebookPromoAIService.validate_public_image_url("http://localhost/promo.png"),
        )
        self.assertIn(
            "private",
            FacebookPromoAIService.validate_public_image_url("https://10.0.0.5/promo.png"),
        )
        self.assertIsNone(FacebookPromoAIService.validate_public_image_url("https://cdn.example.com/promo.png"))

    def test_build_page_validation_request_shape(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            page_id="123",
            page_access_token="secret-token",
        )
        request = FacebookPromoAIService.build_page_validation_request(profile)
        self.assertIsNotNone(request)
        self.assertEqual(request.method, "GET")
        self.assertTrue(request.url.endswith("/123"))
        self.assertEqual(request.headers["Authorization"], "Bearer <PAGE_ACCESS_TOKEN>")
        self.assertEqual(request.payload["fields"], "id,name")

    def test_access_validation_dry_run_blocks_without_access(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService()
            result = await service.build_access_validation_dry_run(1)
            self.assertFalse(result.ok)
            self.assertIsNone(result.request)

        asyncio.run(run())

    def test_graph_adapter_disabled_blocks_network_calls(self) -> None:
        async def run() -> None:
            adapter = FacebookGraphAdapter(enabled=False)
            request = FacebookPromoAIService.build_page_validation_request(
                FacebookPromoProfile(telegram_user_id=1, page_id="123", page_access_token="token")
            )
            result = await adapter.execute(request, "token")
            self.assertFalse(result.ok)
            self.assertIn("disabled", result.message.lower())

        asyncio.run(run())

    def test_validate_page_access_uses_injected_adapter(self) -> None:
        class FakeAdapter:
            async def execute(self, graph_request, access_token):
                self.graph_request = graph_request
                self.access_token = access_token
                return FacebookGraphResponse(True, 200, "ok", "{\"id\":\"123\"}")

        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            fake = FakeAdapter()
            service = FacebookPromoAIService(redis_client=MemoryRedis(), graph_adapter=fake)
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                page_id="123",
                page_access_token="secret-token",
            )
            await service.save_profile(profile)
            result = await service.validate_page_access(1)
            self.assertTrue(result.ok)
            self.assertEqual(fake.access_token, "secret-token")
            self.assertTrue(fake.graph_request.url.endswith("/123"))

        asyncio.run(run())

    def test_publish_safety_status_reports_graph_and_access_blockers(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService()
            status = await service.build_publish_safety_status(1)
            self.assertFalse(status.live_enabled)
            self.assertFalse(status.access_ready)
            self.assertIn("FACEBOOK_PROMO_GRAPH_API_ENABLED=true", status.blockers[0])
            self.assertIn("Page ID is missing.", status.blockers)

        asyncio.run(run())

    def test_publish_safety_status_ready_when_graph_and_access_are_ready(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

        async def run() -> None:
            service = FacebookPromoAIService(redis_client=MemoryRedis(), graph_api_enabled=True)
            await service.save_profile(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    page_id="123",
                    page_access_token="EAA" + "x" * 40,
                )
            )
            status = await service.build_publish_safety_status(1)
            self.assertTrue(status.live_enabled)
            self.assertTrue(status.access_ready)
            self.assertEqual(status.blockers, [])

        asyncio.run(run())

    def test_extract_facebook_post_id(self) -> None:
        self.assertEqual(FacebookPromoAIService.extract_facebook_post_id('{"id":"123_456"}'), "123_456")
        self.assertEqual(FacebookPromoAIService.extract_facebook_post_id('{"post_id":"789"}'), "789")
        self.assertIsNone(FacebookPromoAIService.extract_facebook_post_id("not-json"))

    def test_publish_campaign_marks_campaign_published(self) -> None:
        class FakeAdapter:
            async def execute(self, graph_request, access_token):
                return FacebookGraphResponse(True, 200, "ok", '{"id":"123_456"}')

        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            draft_json = json.dumps(
                {
                    "headline": "Premium Ladies Bag",
                    "primary_copy": "Main copy",
                    "short_copy": "Short copy",
                    "cta": "Inbox now",
                    "hashtags": "#LadiesBag",
                    "image_concept": "Premium visual",
                }
            )
            service = FacebookPromoAIService(redis_client=MemoryRedis(), graph_adapter=FakeAdapter())
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                page_id="123",
                page_access_token="token",
                saved_campaigns_json=json.dumps(
                    [
                        asdict(
                            SavedPromoCampaign(
                                title="Premium Ladies Bag",
                                goal="Product Sale",
                                topic="Ladies bag",
                                created_at="2026-05-21",
                                draft_json=draft_json,
                                status="READY_TO_PUBLISH",
                            )
                        )
                    ]
                ),
            )
            await service.save_profile(profile)
            result = await service.publish_campaign(1, 0)
            self.assertTrue(result.ok)
            campaigns = await service.list_saved_campaigns(1)
            self.assertEqual(campaigns[0].status, "PUBLISHED")
            self.assertEqual(campaigns[0].facebook_post_id, "123_456")
            self.assertIsNotNone(campaigns[0].published_at)

        asyncio.run(run())

    def test_campaign_publish_dry_run_uses_saved_image_for_photo_post(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

        async def run() -> None:
            draft_json = json.dumps(
                {
                    "headline": "Premium Ladies Bag",
                    "primary_copy": "Main copy",
                    "short_copy": "Short copy",
                    "cta": "Inbox now",
                    "hashtags": "#LadiesBag",
                    "image_concept": "Premium visual",
                }
            )
            image_json = json.dumps(
                asdict(
                    GeneratedPromoImage(
                        model="z-image-turbo",
                        prompt="Create product image",
                        image_urls=["https://cdn.example.com/promo.png"],
                        created_at="2026-05-21 10:00:00",
                    )
                )
            )
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            await service.save_profile(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    page_id="123",
                    page_access_token="token",
                    saved_campaigns_json=json.dumps(
                        [
                            asdict(
                                SavedPromoCampaign(
                                    title="Premium Ladies Bag",
                                    goal="Product Sale",
                                    topic="Ladies bag",
                                    created_at="2026-05-21",
                                    draft_json=draft_json,
                                    status="READY_TO_PUBLISH",
                                    image_json=image_json,
                                )
                            )
                        ]
                    ),
                )
            )

            result = await service.build_campaign_publish_dry_run(1, 0)

            self.assertTrue(result.ok)
            self.assertIsNotNone(result.request)
            self.assertTrue(result.request.url.endswith("/123/photos"))
            self.assertEqual(result.request.payload["url"], "https://cdn.example.com/promo.png")
            self.assertIn("Premium Ladies Bag", result.request.payload["caption"])

        asyncio.run(run())

    def test_campaign_publish_dry_run_blocks_invalid_saved_image_url(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

        async def run() -> None:
            draft_json = json.dumps(
                {
                    "headline": "Premium Ladies Bag",
                    "primary_copy": "Main copy",
                    "short_copy": "Short copy",
                    "cta": "Inbox now",
                    "hashtags": "#LadiesBag",
                    "image_concept": "Premium visual",
                }
            )
            image_json = json.dumps(
                asdict(
                    GeneratedPromoImage(
                        model="z-image-turbo",
                        prompt="Create product image",
                        image_urls=["https://127.0.0.1/promo.png"],
                        created_at="2026-05-21 10:00:00",
                    )
                )
            )
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            await service.save_profile(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    page_id="123",
                    page_access_token="token",
                    saved_campaigns_json=json.dumps(
                        [
                            asdict(
                                SavedPromoCampaign(
                                    title="Premium Ladies Bag",
                                    goal="Product Sale",
                                    topic="Ladies bag",
                                    created_at="2026-05-21",
                                    draft_json=draft_json,
                                    status="READY_TO_PUBLISH",
                                    image_json=image_json,
                                )
                            )
                        ]
                    ),
                )
            )

            result = await service.build_campaign_publish_dry_run(1, 0)

            self.assertFalse(result.ok)
            self.assertIsNone(result.request)
            self.assertIn("not publish-ready", result.message)

        asyncio.run(run())

    def test_campaign_publish_checklist_reports_type_and_blockers(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

        async def run() -> None:
            draft_json = json.dumps(
                {
                    "headline": "Premium Ladies Bag",
                    "primary_copy": "Main copy",
                    "short_copy": "Short copy",
                    "cta": "Inbox now",
                    "hashtags": "#LadiesBag",
                    "image_concept": "Premium visual",
                }
            )
            image_json = json.dumps(
                asdict(
                    GeneratedPromoImage(
                        model="z-image-turbo",
                        prompt="Create product image",
                        image_urls=["https://cdn.example.com/promo.png"],
                        created_at="2026-05-21 10:00:00",
                    )
                )
            )
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            await service.save_profile(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    page_id="123",
                    page_access_token="EAA" + "x" * 40,
                    saved_campaigns_json=json.dumps(
                        [
                            asdict(
                                SavedPromoCampaign(
                                    title="Premium Ladies Bag",
                                    goal="Product Sale",
                                    topic="Ladies bag",
                                    created_at="2026-05-21",
                                    draft_json=draft_json,
                                    status="READY_TO_PUBLISH",
                                    image_json=image_json,
                                )
                            )
                        ]
                    ),
                )
            )

            checklist = await service.build_campaign_publish_checklist(1, 0)

            self.assertFalse(checklist.live_ready)
            self.assertEqual(checklist.publish_type, "photo post")
            self.assertIn("Image URL: public HTTPS format", checklist.checks)
            self.assertIn("Graph live posting is disabled; use dry-run only.", checklist.blockers)

        asyncio.run(run())

    def test_campaign_publish_checklist_ready_when_graph_and_access_ready(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

        async def run() -> None:
            draft_json = json.dumps(
                {
                    "headline": "Premium Ladies Bag",
                    "primary_copy": "Main copy",
                    "short_copy": "Short copy",
                    "cta": "Inbox now",
                    "hashtags": "#LadiesBag",
                    "image_concept": "Premium visual",
                }
            )
            service = FacebookPromoAIService(redis_client=MemoryRedis(), graph_api_enabled=True)
            await service.save_profile(
                FacebookPromoProfile(
                    telegram_user_id=1,
                    page_id="123",
                    page_access_token="EAA" + "x" * 40,
                    saved_campaigns_json=json.dumps(
                        [
                            asdict(
                                SavedPromoCampaign(
                                    title="Premium Ladies Bag",
                                    goal="Product Sale",
                                    topic="Ladies bag",
                                    created_at="2026-05-21",
                                    draft_json=draft_json,
                                    status="READY_TO_PUBLISH",
                                )
                            )
                        ]
                    ),
                )
            )

            checklist = await service.build_campaign_publish_checklist(1, 0)

            self.assertTrue(checklist.live_ready)
            self.assertEqual(checklist.publish_type, "text post")
            self.assertEqual(checklist.blockers, [])

        asyncio.run(run())

    def test_build_publish_message_contains_core_parts(self) -> None:
        draft = FacebookPromoAIService.generate_draft(
            FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
            ),
            FacebookPromoAIService.generate_strategy_plan(
                PendingFacebookPromoAction(
                    stage="await_plan_review",
                    goal_key="SALE",
                    goal_label="Product Sale",
                    topic="Ladies bag",
                    audience="Women 20-35",
                    image_mode="NEEDED",
                    selected_angle="PREMIUM_VALUE",
                )
            ),
        )
        message = FacebookPromoAIService.build_publish_message(draft)
        self.assertIn(draft.headline, message)
        self.assertIn(draft.cta, message)
        self.assertIn(draft.hashtags, message)

    def test_build_draft_variants_returns_expected_keys(self) -> None:
        base = FacebookPromoAIService.generate_draft(
            FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
            ),
            FacebookPromoAIService.generate_strategy_plan(
                PendingFacebookPromoAction(
                    stage="await_plan_review",
                    goal_key="SALE",
                    goal_label="Product Sale",
                    topic="Ladies bag",
                    audience="Women 20-35",
                    image_mode="NEEDED",
                    selected_angle="PREMIUM_VALUE",
                )
            ),
        )
        variants = FacebookPromoAIService.build_draft_variants(base)
        self.assertEqual(set(variants.keys()), {"Base", "Premium", "Short", "Urgent"})

    def test_parse_saved_campaigns_roundtrip(self) -> None:
        payload = json.dumps(
            [
                asdict(
                    SavedPromoCampaign(
                        title="Premium Ladies Bag",
                        goal="Product Sale",
                        topic="Ladies bag",
                        created_at="2026-05-20 12:00:00",
                        draft_json=json.dumps(
                            {
                                "headline": "Premium Ladies Bag",
                                "primary_copy": "Main copy",
                                "short_copy": "Short copy",
                                "cta": "Inbox now",
                                "hashtags": "#LadiesBag",
                                "image_concept": "Premium visual",
                            }
                        ),
                        status="READY_TO_PUBLISH",
                    )
                )
            ]
        )
        campaigns = FacebookPromoAIService.parse_saved_campaigns(payload)
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0].title, "Premium Ladies Bag")
        self.assertEqual(campaigns[0].status, "READY_TO_PUBLISH")
        parsed_draft = FacebookPromoAIService.parse_draft(campaigns[0].draft_json)
        self.assertIsNotNone(parsed_draft)

    def test_load_saved_campaign_as_current_draft_without_storage(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService()
            loaded = await service.load_saved_campaign_as_current_draft(1, 0)
            self.assertIsNone(loaded)

        asyncio.run(run())

    def test_image_model_routing_blocks_free_premium_models(self) -> None:
        self.assertEqual(FacebookPromoAIService.resolve_image_user_tier(set()), "FREE")
        self.assertEqual(FacebookPromoAIService.select_allowed_image_model("FREE"), "z-image-turbo")
        self.assertIsNone(FacebookPromoAIService.select_allowed_image_model("FREE", "qwen-image-2.0"))
        self.assertEqual(FacebookPromoAIService.select_allowed_image_model("FREE", "wan2.7-image"), "wan2.7-image")

    def test_image_model_routing_allows_paid_quality_models(self) -> None:
        self.assertEqual(FacebookPromoAIService.resolve_image_user_tier({"PAID_USER"}), "PAID")
        self.assertEqual(FacebookPromoAIService.select_allowed_image_model("PAID"), "qwen-image-2.0")
        self.assertEqual(
            FacebookPromoAIService.select_allowed_image_model("PAID", "qwen-image-2.0-pro"),
            "qwen-image-2.0-pro",
        )
        self.assertIsNone(FacebookPromoAIService.select_allowed_image_model("PAID", "z-image-turbo"))

    def test_image_model_routing_allows_admin_safe_test_models(self) -> None:
        self.assertEqual(FacebookPromoAIService.resolve_image_user_tier({"OWNER"}), "ADMIN")
        self.assertEqual(FacebookPromoAIService.select_allowed_image_model("ADMIN"), "z-image-turbo")
        self.assertEqual(
            FacebookPromoAIService.select_allowed_image_model("ADMIN", "wan2.7-image"),
            "wan2.7-image",
        )
        self.assertEqual(
            FacebookPromoAIService.select_allowed_image_model("ADMIN", "qwen-image-2.0"),
            "qwen-image-2.0",
        )

    def test_image_policy_blocks_when_api_disabled(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(alibaba_image_api_enabled=False)
            policy = await service.build_image_generation_policy(1, set())
            self.assertFalse(policy.allowed)
            self.assertEqual(policy.model, "z-image-turbo")
            self.assertIn("disabled", policy.message.lower())

        asyncio.run(run())

    def test_image_policy_blocks_free_monthly_cap(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

            def incr(self, key):
                self.values[key] = str(int(self.values.get(key, 0)) + 1)
                return int(self.values[key])

            def expire(self, key, ttl):
                self.values[f"ttl:{key}"] = ttl

        async def run() -> None:
            redis = MemoryRedis()
            service = FacebookPromoAIService(
                redis_client=redis,
                alibaba_image_api_enabled=True,
                alibaba_free_monthly_image_cap=1,
            )
            await service.record_successful_image_generation(7)
            policy = await service.build_image_generation_policy(7, set())
            self.assertFalse(policy.allowed)
            self.assertEqual(policy.monthly_used, 1)
            self.assertIn("monthly image limit", policy.message.lower())

        asyncio.run(run())

    def test_image_policy_allows_paid_until_paid_cap(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(
                alibaba_image_api_enabled=True,
                alibaba_paid_monthly_image_cap=3,
                alibaba_image_admin_live_only=False,
            )
            policy = await service.build_image_generation_policy(7, {"PAID_USER"}, "qwen-image-plus")
            self.assertTrue(policy.allowed)
            self.assertEqual(policy.user_tier, "PAID")
            self.assertEqual(policy.model, "qwen-image-plus")
            self.assertEqual(policy.monthly_limit, 3)

        asyncio.run(run())

    def test_image_policy_blocks_non_admin_when_live_rollout_is_admin_only(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(
                alibaba_image_api_enabled=True,
                alibaba_image_dry_run=False,
                alibaba_image_admin_live_only=True,
            )
            policy = await service.build_image_generation_policy(7, {"PAID_USER"}, "qwen-image-2.0")
            self.assertFalse(policy.allowed)
            self.assertIn("admin-only", policy.message.lower())

        asyncio.run(run())

    def test_image_policy_allows_admin_live_test(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(
                alibaba_image_api_enabled=True,
                alibaba_image_dry_run=False,
                alibaba_image_admin_live_only=True,
            )
            policy = await service.build_image_generation_policy(7, {"OWNER"})
            self.assertTrue(policy.allowed)
            self.assertEqual(policy.user_tier, "ADMIN")
            self.assertEqual(policy.model, "z-image-turbo")

        asyncio.run(run())

    def test_image_live_preflight_reports_safe_blockers(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(
                alibaba_image_api_enabled=False,
                alibaba_image_dry_run=True,
                alibaba_image_admin_live_only=True,
            )
            preflight = await service.build_image_live_preflight(7, {"OWNER"})
            self.assertFalse(preflight.ready)
            self.assertIn("Set ALIBABA_IMAGE_API_ENABLED=true.", preflight.blockers)
            self.assertIn("Set ALIBABA_IMAGE_DRY_RUN=false for a real one-image test.", preflight.blockers)

        asyncio.run(run())

    def test_image_live_preflight_ready_for_admin_only_live_test(self) -> None:
        async def run() -> None:
            service = FacebookPromoAIService(
                alibaba_image_api_enabled=True,
                alibaba_image_dry_run=False,
                alibaba_image_admin_live_only=True,
            )
            preflight = await service.build_image_live_preflight(7, {"OWNER"})
            self.assertTrue(preflight.ready)
            self.assertEqual(preflight.blockers, [])

        asyncio.run(run())

    def test_build_image_prompt_uses_draft_and_profile_context(self) -> None:
        profile = FacebookPromoProfile(
            telegram_user_id=1,
            brand_notes="Premium bag shop with elegant styling",
            strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35\nImage mode: NEEDED",
        )
        draft = PromoDraft(
            headline="Premium Ladies Bag",
            primary_copy="Main copy",
            short_copy="Short copy",
            cta="Inbox now",
            hashtags="#LadiesBag",
            image_concept="Minimal studio product image with warm lighting",
        )
        prompt = FacebookPromoAIService.build_image_prompt(profile, draft)
        self.assertIn("Ladies bag", prompt)
        self.assertIn("Women 20-35", prompt)
        self.assertIn("Minimal studio product image", prompt)

    def test_build_image_generation_preview_returns_policy_and_prompt(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            service = FacebookPromoAIService(redis_client=MemoryRedis(), alibaba_image_api_enabled=False)
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                brand_notes="Premium bag shop",
                strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35\nImage mode: NEEDED",
                last_draft_json=json.dumps(
                    asdict(
                        PromoDraft(
                            headline="Premium Ladies Bag",
                            primary_copy="Main copy",
                            short_copy="Short copy",
                            cta="Inbox now",
                            hashtags="#LadiesBag",
                            image_concept="Clean ecommerce image",
                        )
                    )
                ),
            )
            await service.save_profile(profile)
            policy, prompt = await service.build_image_generation_preview(1, set())
            self.assertFalse(policy.allowed)
            self.assertEqual(policy.model, "z-image-turbo")
            self.assertIn("Premium Ladies Bag", prompt)

        asyncio.run(run())

    def test_alibaba_image_adapter_builds_qwen_request_without_calling_api(self) -> None:
        adapter = AlibabaImageAdapter(api_key="secret", enabled=False, dry_run=True)
        image_request = adapter.build_request("qwen-image-2.0", "Create a product image")
        self.assertTrue(image_request.url.endswith("/services/aigc/multimodal-generation/generation"))
        self.assertEqual(image_request.payload["model"], "qwen-image-2.0")
        self.assertEqual(image_request.payload["parameters"]["size"], "1024*1024")
        self.assertFalse(image_request.payload["parameters"]["watermark"])

    def test_alibaba_image_adapter_builds_wan_request_without_calling_api(self) -> None:
        adapter = AlibabaImageAdapter(api_key="secret", enabled=False, dry_run=True)
        image_request = adapter.build_request("wan2.7-image", "Create a product image")
        self.assertEqual(image_request.payload["model"], "wan2.7-image")
        self.assertEqual(image_request.payload["parameters"]["size"], "2K")
        self.assertEqual(image_request.payload["parameters"]["n"], 1)

    def test_alibaba_image_adapter_extracts_nested_image_urls(self) -> None:
        body = json.dumps(
            {
                "output": {
                    "choices": [
                        {"message": {"content": [{"image_url": "https://example.com/a.png"}]}},
                        {"url": "https://example.com/b.png"},
                    ]
                }
            }
        )
        self.assertEqual(
            AlibabaImageAdapter.extract_image_urls(body),
            ["https://example.com/a.png", "https://example.com/b.png"],
        )

    def test_generate_campaign_image_dry_run_does_not_increment_usage(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

            def incr(self, key):
                self.values[key] = str(int(self.values.get(key, 0)) + 1)
                return int(self.values[key])

            def expire(self, key, ttl):
                self.values[f"ttl:{key}"] = ttl

        async def run() -> None:
            service = FacebookPromoAIService(
                redis_client=MemoryRedis(),
                alibaba_image_api_enabled=True,
                alibaba_image_dry_run=True,
            )
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35\nImage mode: NEEDED",
                last_draft_json=json.dumps(
                    asdict(
                        PromoDraft(
                            headline="Premium Ladies Bag",
                            primary_copy="Main copy",
                            short_copy="Short copy",
                            cta="Inbox now",
                            hashtags="#LadiesBag",
                            image_concept="Clean ecommerce image",
                        )
                    )
                ),
            )
            await service.save_profile(profile)
            result = await service.generate_campaign_image(1, set())
            self.assertFalse(result.ok)
            self.assertIn("dry-run", result.message.lower())
            self.assertEqual(await service.get_monthly_image_usage(1), 0)

        asyncio.run(run())

    def test_generate_campaign_image_success_increments_usage(self) -> None:
        class FakeImageAdapter:
            def build_request(self, model, prompt):
                return AlibabaImageAdapter().build_request(model, prompt)

            async def generate(self, model, prompt):
                return AlibabaImageResult(True, "ok", ["https://example.com/a.png"])

        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

            def incr(self, key):
                self.values[key] = str(int(self.values.get(key, 0)) + 1)
                return int(self.values[key])

            def expire(self, key, ttl):
                self.values[f"ttl:{key}"] = ttl

        async def run() -> None:
            service = FacebookPromoAIService(
                redis_client=MemoryRedis(),
                alibaba_image_api_enabled=True,
                alibaba_image_dry_run=False,
                alibaba_image_admin_live_only=False,
                image_adapter=FakeImageAdapter(),
            )
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35\nImage mode: NEEDED",
                last_draft_json=json.dumps(
                    asdict(
                        PromoDraft(
                            headline="Premium Ladies Bag",
                            primary_copy="Main copy",
                            short_copy="Short copy",
                            cta="Inbox now",
                            hashtags="#LadiesBag",
                            image_concept="Clean ecommerce image",
                        )
                    )
                ),
            )
            await service.save_profile(profile)
            result = await service.generate_campaign_image(1, set())
            self.assertTrue(result.ok)
            self.assertEqual(await service.get_monthly_image_usage(1), 1)
            saved = await service.get_profile(1)
            generated_image = service.parse_generated_image(saved.last_image_json)
            self.assertIsNotNone(generated_image)
            self.assertEqual(generated_image.model, "z-image-turbo")
            self.assertEqual(generated_image.image_urls, ["https://example.com/a.png"])

        asyncio.run(run())

    def test_save_campaign_copies_generated_image_metadata(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            draft = PromoDraft(
                headline="Premium Ladies Bag",
                primary_copy="Main copy",
                short_copy="Short copy",
                cta="Inbox now",
                hashtags="#LadiesBag",
                image_concept="Clean ecommerce image",
            )
            image = GeneratedPromoImage(
                model="z-image-turbo",
                prompt="Create image",
                image_urls=["https://example.com/a.png"],
                created_at="2026-05-21 12:00:00",
            )
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35",
                last_draft_json=json.dumps(asdict(draft)),
                last_image_json=json.dumps(asdict(image)),
            )
            await service.save_profile(profile)
            campaign = await service.save_current_draft_as_campaign(1)
            self.assertIsNotNone(campaign)
            generated_image = service.parse_generated_image(campaign.image_json)
            self.assertIsNotNone(generated_image)
            self.assertEqual(generated_image.image_urls, ["https://example.com/a.png"])

        asyncio.run(run())

    def test_refining_draft_clears_stale_generated_image(self) -> None:
        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            service = FacebookPromoAIService(redis_client=MemoryRedis())
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                strategy_notes="Goal: Product Sale\nTopic: Ladies bag\nAudience: Women 20-35",
                last_draft_json=json.dumps(
                    asdict(
                        PromoDraft(
                            headline="Premium Ladies Bag",
                            primary_copy="Main copy",
                            short_copy="Short copy",
                            cta="Inbox now",
                            hashtags="#LadiesBag",
                            image_concept="Clean ecommerce image",
                        )
                    )
                ),
                last_image_json=json.dumps(
                    asdict(
                        GeneratedPromoImage(
                            model="z-image-turbo",
                            prompt="Create image",
                            image_urls=["https://example.com/a.png"],
                            created_at="2026-05-21 12:00:00",
                        )
                    )
                ),
            )
            await service.save_profile(profile)
            await service.refine_saved_draft(1, "make it shorter")
            updated = await service.get_profile(1)
            self.assertIsNone(updated.last_image_json)

        asyncio.run(run())

    def test_parse_ai_draft_payload_accepts_json_fences(self) -> None:
        payload = """```json
{
  "headline": "Fresh Eid Offer",
  "primary_copy": "A clear offer for the right audience.",
  "short_copy": "Fresh Eid Offer. Inbox now.",
  "cta": "Inbox now to order.",
  "hashtags": "#EidOffer #ShopNow",
  "image_concept": "Clean product visual with offer text."
}
```"""
        draft = FacebookPromoAIService.parse_ai_draft_payload(payload)
        self.assertIsNotNone(draft)
        self.assertEqual(draft.headline, "Fresh Eid Offer")
        self.assertIn("#EidOffer", draft.hashtags)

    def test_generate_and_save_draft_uses_injected_text_adapter(self) -> None:
        class FakeTextAdapter:
            def __init__(self) -> None:
                self.prompt = ""

            async def generate_json(self, prompt):
                self.prompt = prompt
                return json.dumps(
                    {
                        "headline": "AI Premium Bag",
                        "primary_copy": "AI-made premium copy.",
                        "short_copy": "AI Premium Bag. Inbox now.",
                        "cta": "Inbox now to order.",
                        "hashtags": "#PremiumBag #ShopNow",
                        "image_concept": "Premium studio visual.",
                    }
                )

        class MemoryRedis:
            def __init__(self) -> None:
                self.values = {}

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.values[key] = value

            def delete(self, key):
                self.values.pop(key, None)

        async def run() -> None:
            adapter = FakeTextAdapter()
            service = FacebookPromoAIService(redis_client=MemoryRedis(), text_adapter=adapter)
            profile = FacebookPromoProfile(
                telegram_user_id=1,
                brand_notes="Premium bag page",
                strategy_notes=(
                    "Goal: Product Sale\n"
                    "User request: Make a better sale post\n"
                    "Topic: Ladies bag\n"
                    "Audience: Women 20-35\n"
                    "Image mode: NEEDED"
                ),
                last_plan_json=json.dumps(
                    asdict(
                        FacebookPromoAIService.generate_strategy_plan(
                            PendingFacebookPromoAction(
                                stage="await_plan_review",
                                goal_key="SALE",
                                goal_label="Product Sale",
                                topic="Ladies bag",
                                audience="Women 20-35",
                                image_mode="NEEDED",
                                selected_angle="PREMIUM_VALUE",
                            )
                        )
                    )
                ),
            )
            await service.save_profile(profile)
            draft = await service.generate_and_save_draft(1)
            self.assertIsNotNone(draft)
            self.assertEqual(draft.headline, "AI Premium Bag")
            self.assertIn("Ladies bag", adapter.prompt)
            saved = await service.get_profile(1)
            self.assertIn("AI Premium Bag", saved.last_draft_json)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
