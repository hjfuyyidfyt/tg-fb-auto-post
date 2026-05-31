from __future__ import annotations

import asyncio
import ipaddress
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib import error, parse, request


@dataclass(slots=True)
class FacebookPromoProfile:
    telegram_user_id: int
    status: str = "INACTIVE"
    page_id: str | None = None
    page_access_token: str | None = None
    brand_notes: str | None = None
    strategy_notes: str | None = None
    preferred_tone: str | None = None
    preferred_emoji_style: str | None = None
    preferred_cta_style: str | None = None
    preferred_image_style: str | None = None
    last_goal: str | None = None
    last_plan_json: str | None = None
    last_draft_json: str | None = None
    last_image_json: str | None = None
    saved_campaigns_json: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class PendingFacebookPromoAction:
    stage: str
    user_request: str | None = None
    goal_key: str | None = None
    goal_label: str | None = None
    topic: str | None = None
    audience: str | None = None
    image_mode: str | None = None
    selected_angle: str | None = None
    plan_feedback: str | None = None


@dataclass(slots=True)
class PromoRecommendation:
    key: str
    title: str
    summary: str


@dataclass(slots=True)
class PromoStrategyPlan:
    angle_title: str
    positioning: str
    hook_style: str
    copy_direction: str
    cta_direction: str
    image_direction: str


@dataclass(slots=True)
class PromoDraft:
    headline: str
    primary_copy: str
    short_copy: str
    cta: str
    hashtags: str
    image_concept: str


@dataclass(slots=True)
class GeneratedPromoImage:
    model: str
    prompt: str
    image_urls: list[str]
    created_at: str


@dataclass(slots=True)
class SavedPromoCampaign:
    title: str
    goal: str
    topic: str
    created_at: str
    draft_json: str
    status: str = "DRAFT"
    published_at: str | None = None
    facebook_post_id: str | None = None
    publish_response_json: str | None = None
    image_json: str | None = None


@dataclass(slots=True)
class FacebookGraphRequest:
    method: str
    url: str
    headers: dict[str, str]
    payload: dict[str, str]


@dataclass(slots=True)
class FacebookPublishDryRun:
    ok: bool
    message: str
    request: FacebookGraphRequest | None = None


@dataclass(slots=True)
class FacebookGraphResponse:
    ok: bool
    status_code: int | None
    message: str
    body: str | None = None


@dataclass(slots=True)
class FacebookAccessReadiness:
    ready: bool
    page_id_saved: bool
    token_saved: bool
    token_preview: str
    issues: list[str]
    next_step: str


@dataclass(slots=True)
class FacebookPublishSafetyStatus:
    live_enabled: bool
    graph_version: str
    access_ready: bool
    checks: list[str]
    blockers: list[str]


@dataclass(slots=True)
class FacebookCampaignPublishChecklist:
    live_ready: bool
    publish_type: str
    checks: list[str]
    blockers: list[str]


@dataclass(slots=True)
class ImageGenerationPolicy:
    allowed: bool
    user_tier: str
    model: str | None
    fallback_models: list[str]
    monthly_used: int
    monthly_limit: int
    global_used: int
    global_limit: int
    dry_run: bool
    message: str


@dataclass(slots=True)
class AlibabaImageRequest:
    model: str
    prompt: str
    url: str
    payload: dict[str, object]


@dataclass(slots=True)
class AlibabaImageResult:
    ok: bool
    message: str
    image_urls: list[str]
    status_code: int | None = None
    body: str | None = None
    request: AlibabaImageRequest | None = None


@dataclass(slots=True)
class ImageLivePreflight:
    ready: bool
    checks: list[str]
    blockers: list[str]


class FacebookGraphAdapter:
    def __init__(self, enabled: bool = False, timeout_seconds: float = 15.0) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    async def execute(self, graph_request: FacebookGraphRequest, access_token: str) -> FacebookGraphResponse:
        if not self.enabled:
            return FacebookGraphResponse(
                ok=False,
                status_code=None,
                message="Facebook Graph API is disabled. Dry-run mode only.",
            )
        return await asyncio.to_thread(self._execute_sync, graph_request, access_token)

    def _execute_sync(self, graph_request: FacebookGraphRequest, access_token: str) -> FacebookGraphResponse:
        url = graph_request.url
        data: bytes | None = None
        if graph_request.method.upper() == "GET" and graph_request.payload:
            query = parse.urlencode(graph_request.payload)
            url = f"{url}?{query}"
        elif graph_request.payload:
            data = parse.urlencode(graph_request.payload).encode("utf-8")

        headers = {
            **graph_request.headers,
            "Authorization": f"Bearer {access_token}",
        }
        req = request.Request(url, data=data, headers=headers, method=graph_request.method.upper())
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read(2000).decode("utf-8", errors="replace")
                return FacebookGraphResponse(True, response.status, "Facebook Graph API request succeeded.", body)
        except error.HTTPError as exc:
            body = exc.read(2000).decode("utf-8", errors="replace")
            return FacebookGraphResponse(False, exc.code, "Facebook Graph API returned an error.", body)
        except error.URLError as exc:
            return FacebookGraphResponse(False, None, f"Facebook Graph API request failed: {exc.reason}")


class GeminiTextAdapter:
    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.5-flash",
        timeout_seconds: float = 25.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "gemini-2.5-flash-lite"
        self.fallback_model = fallback_model.strip() or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds

    async def generate_json(self, prompt: str) -> str | None:
        if not self.api_key:
            return None
        models = [self.model]
        if self.fallback_model and self.fallback_model not in models:
            models.append(self.fallback_model)
        for model in models:
            result = await asyncio.to_thread(self._generate_json_sync, model, prompt)
            if result:
                return result
        return None

    def _generate_json_sync(self, model: str, prompt: str) -> str | None:
        model_name = model.removeprefix("models/").strip("/")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{parse.quote(model_name, safe='')}:generateContent?key={parse.quote(self.api_key, safe='')}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.75,
                "maxOutputTokens": 1400,
                "responseMimeType": "application/json",
            },
        }
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read(8000).decode("utf-8", errors="replace")
        except (error.HTTPError, error.URLError, TimeoutError):
            return None

        try:
            response_payload = json.loads(body)
            parts = response_payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            return None
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        return text or None


class AlibabaImageAdapter:
    def __init__(
        self,
        api_key: str = "",
        enabled: bool = False,
        dry_run: bool = True,
        base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.enabled = enabled
        self.dry_run = dry_run
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def build_request(self, model: str, prompt: str) -> AlibabaImageRequest:
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": self.parameters_for_model(model),
        }
        return AlibabaImageRequest(
            model=model,
            prompt=prompt,
            url=f"{self.base_url}/services/aigc/multimodal-generation/generation",
            payload=payload,
        )

    async def generate(self, model: str, prompt: str) -> AlibabaImageResult:
        image_request = self.build_request(model, prompt)
        if not self.enabled:
            return AlibabaImageResult(False, "Alibaba image API is disabled.", [], request=image_request)
        if self.dry_run:
            return AlibabaImageResult(False, "Alibaba image API dry-run mode is enabled.", [], request=image_request)
        if not self.api_key:
            return AlibabaImageResult(False, "Alibaba API key is missing.", [], request=image_request)
        return await asyncio.to_thread(self._generate_sync, image_request)

    def _generate_sync(self, image_request: AlibabaImageRequest) -> AlibabaImageResult:
        req = request.Request(
            image_request.url,
            data=json.dumps(image_request.payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read(12000).decode("utf-8", errors="replace")
                image_urls = self.extract_image_urls(body)
                return AlibabaImageResult(
                    bool(image_urls),
                    "Alibaba image generation succeeded." if image_urls else "Alibaba response did not include an image URL.",
                    image_urls,
                    response.status,
                    body,
                    image_request,
                )
        except error.HTTPError as exc:
            body = exc.read(12000).decode("utf-8", errors="replace")
            return AlibabaImageResult(False, "Alibaba image API returned an error.", [], exc.code, body, image_request)
        except error.URLError as exc:
            return AlibabaImageResult(False, f"Alibaba image API request failed: {exc.reason}", [], None, None, image_request)

    @staticmethod
    def parameters_for_model(model: str) -> dict[str, object]:
        if model.startswith("wan2.7-image"):
            return {"size": "2K", "n": 1, "watermark": False, "thinking_mode": True}
        if model.startswith("qwen-image"):
            return {
                "negative_prompt": "low quality, blurry, distorted text, distorted hands, malformed faces, messy layout",
                "prompt_extend": True,
                "watermark": False,
                "size": "1024*1024",
            }
        return {"watermark": False, "size": "1024*1024"}

    @staticmethod
    def extract_image_urls(body: str | None) -> list[str]:
        if not body:
            return []
        try:
            payload = json.loads(body)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        urls: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"url", "image_url", "output_url"} and isinstance(item, str) and item.startswith("http"):
                        urls.append(item)
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return urls


class FacebookPromoAIService:
    FREE_IMAGE_MODELS = ["z-image-turbo", "wan2.7-image"]
    PAID_IMAGE_MODELS = ["qwen-image-2.0", "qwen-image-plus", "qwen-image-2.0-pro", "qwen-image-max"]
    ADMIN_IMAGE_MODELS = [*FREE_IMAGE_MODELS, *PAID_IMAGE_MODELS]
    PREMIUM_IMAGE_MODELS = {"qwen-image-max", "qwen-image-2.0-pro", "wan2.7-image-pro", "qwen-image-plus", "qwen-image-2.0"}
    IMAGE_EDIT_MODELS = ["qwen-image-edit", "qwen-image-edit-plus", "qwen-image-edit-max"]

    def __init__(
        self,
        redis_client: object | None = None,
        graph_api_enabled: bool = False,
        graph_version: str = "v24.0",
        graph_adapter: FacebookGraphAdapter | None = None,
        gemini_api_key: str = "",
        gemini_text_model: str = "gemini-2.5-flash-lite",
        gemini_text_fallback_model: str = "gemini-2.5-flash",
        text_adapter: GeminiTextAdapter | None = None,
        alibaba_api_key: str = "",
        alibaba_image_api_enabled: bool = False,
        alibaba_image_dry_run: bool = True,
        alibaba_image_admin_live_only: bool = True,
        alibaba_image_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1",
        alibaba_free_monthly_image_cap: int = 10,
        alibaba_paid_monthly_image_cap: int = 100,
        alibaba_global_monthly_image_cap: int = 100,
        image_adapter: AlibabaImageAdapter | None = None,
    ) -> None:
        self.redis_client = redis_client
        self.graph_version = graph_version
        self.graph_api_enabled = graph_api_enabled
        self.graph_adapter = graph_adapter or FacebookGraphAdapter(enabled=graph_api_enabled)
        if graph_adapter is not None:
            self.graph_api_enabled = bool(getattr(graph_adapter, "enabled", graph_api_enabled))
        self.text_adapter = text_adapter or GeminiTextAdapter(
            api_key=gemini_api_key,
            model=gemini_text_model,
            fallback_model=gemini_text_fallback_model,
        )
        self.alibaba_image_api_enabled = alibaba_image_api_enabled
        self.alibaba_image_dry_run = alibaba_image_dry_run
        self.alibaba_image_admin_live_only = alibaba_image_admin_live_only
        self.alibaba_free_monthly_image_cap = alibaba_free_monthly_image_cap
        self.alibaba_paid_monthly_image_cap = alibaba_paid_monthly_image_cap
        self.alibaba_global_monthly_image_cap = alibaba_global_monthly_image_cap
        self.image_adapter = image_adapter or AlibabaImageAdapter(
            api_key=alibaba_api_key,
            enabled=alibaba_image_api_enabled,
            dry_run=alibaba_image_dry_run,
            base_url=alibaba_image_base_url,
        )

    async def get_profile(self, telegram_user_id: int) -> FacebookPromoProfile:
        if not self.redis_client:
            return FacebookPromoProfile(telegram_user_id=telegram_user_id)
        payload = await asyncio.to_thread(self.redis_client.get, self._profile_key(telegram_user_id))
        if not payload:
            return FacebookPromoProfile(telegram_user_id=telegram_user_id)
        return FacebookPromoProfile(**json.loads(payload))

    async def save_profile(self, profile: FacebookPromoProfile) -> FacebookPromoProfile:
        profile.updated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        if self.redis_client:
            await asyncio.to_thread(
                self.redis_client.setex,
                self._profile_key(profile.telegram_user_id),
                86400 * 30,
                json.dumps(asdict(profile)),
            )
        return profile

    async def set_pending_stage(self, telegram_user_id: int, stage: str) -> None:
        await self.save_pending_action(telegram_user_id, PendingFacebookPromoAction(stage=stage))

    async def get_pending_action(self, telegram_user_id: int) -> PendingFacebookPromoAction | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._pending_key(telegram_user_id))
        if not payload:
            return None
        return PendingFacebookPromoAction(**json.loads(payload))

    async def clear_pending_action(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._pending_key(telegram_user_id))

    async def save_pending_action(self, telegram_user_id: int, action: PendingFacebookPromoAction) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._pending_key(telegram_user_id),
            1800,
            json.dumps(asdict(action)),
        )

    async def start_new_task(self, telegram_user_id: int) -> None:
        await self.save_pending_action(telegram_user_id, PendingFacebookPromoAction(stage="await_request"))

    async def save_user_request(self, telegram_user_id: int, pending: PendingFacebookPromoAction, text: str) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_goal",
                user_request=text.strip(),
            ),
        )

    async def save_goal(
        self,
        telegram_user_id: int,
        pending: PendingFacebookPromoAction,
        goal_key: str,
        goal_label: str,
    ) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_topic",
                user_request=pending.user_request,
                goal_key=goal_key,
                goal_label=goal_label,
            ),
        )

    async def save_topic(self, telegram_user_id: int, pending: PendingFacebookPromoAction, topic: str) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_audience",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=topic.strip(),
            ),
        )

    async def save_audience(self, telegram_user_id: int, pending: PendingFacebookPromoAction, audience: str) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_image_mode",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=audience.strip(),
            ),
        )

    async def save_image_mode(self, telegram_user_id: int, pending: PendingFacebookPromoAction, image_mode: str) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_angle",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=pending.audience,
                image_mode=image_mode,
            ),
        )

    async def save_selected_angle(
        self,
        telegram_user_id: int,
        pending: PendingFacebookPromoAction,
        angle_key: str,
    ) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_plan_review",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=pending.audience,
                image_mode=pending.image_mode,
                selected_angle=angle_key,
            ),
        )

    async def set_plan_feedback(
        self,
        telegram_user_id: int,
        pending: PendingFacebookPromoAction,
        feedback: str,
    ) -> None:
        await self.save_pending_action(
            telegram_user_id,
            PendingFacebookPromoAction(
                stage="await_plan_review",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=pending.audience,
                image_mode=pending.image_mode,
                selected_angle=pending.selected_angle,
                plan_feedback=feedback.strip(),
            ),
        )

    async def merge_task_into_strategy(self, telegram_user_id: int, pending: PendingFacebookPromoAction) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        plan = self.generate_strategy_plan(pending)
        lines = [
            f"Goal: {pending.goal_label or pending.goal_key or 'Not set'}",
            f"User request: {pending.user_request or 'Not set'}",
            f"Topic: {pending.topic or 'Not set'}",
            f"Audience: {pending.audience or 'Not set'}",
            f"Image mode: {pending.image_mode or 'Not set'}",
            f"Recommended angle: {pending.selected_angle or 'Not set'}",
            f"Plan feedback: {pending.plan_feedback or 'Not set'}",
        ]
        profile.last_goal = pending.goal_label or pending.goal_key or profile.last_goal
        profile.last_plan_json = json.dumps(asdict(plan))
        profile.strategy_notes = "\n".join(lines) if not profile.strategy_notes else f"{profile.strategy_notes}\n\n" + "\n".join(lines)
        return await self.save_profile(profile)

    async def generate_and_save_draft(self, telegram_user_id: int) -> PromoDraft | None:
        profile = await self.get_profile(telegram_user_id)
        plan = self.parse_plan(profile.last_plan_json)
        if not plan:
            return None
        draft = await self.generate_ai_draft(profile, plan)
        if not draft:
            draft = self.generate_draft(profile, plan)
        profile.last_draft_json = json.dumps(asdict(draft))
        profile.last_image_json = None
        await self.save_profile(profile)
        return draft

    async def generate_ai_draft(self, profile: FacebookPromoProfile, plan: PromoStrategyPlan) -> PromoDraft | None:
        payload = await self.text_adapter.generate_json(self.build_gemini_draft_prompt(profile, plan))
        return self.parse_ai_draft_payload(payload)

    async def refine_saved_draft(self, telegram_user_id: int, instruction: str) -> PromoDraft | None:
        profile = await self.get_profile(telegram_user_id)
        draft = self.parse_draft(profile.last_draft_json)
        if not draft:
            return None
        refined = self.refine_draft(draft, instruction)
        profile.last_draft_json = json.dumps(asdict(refined))
        profile.last_image_json = None
        if instruction.strip():
            note = f"Draft refine: {instruction.strip()}"
            profile.strategy_notes = note if not profile.strategy_notes else f"{profile.strategy_notes}\n- {note}"
        await self.save_profile(profile)
        return refined

    async def refine_saved_image_concept(self, telegram_user_id: int, instruction: str) -> PromoDraft | None:
        return await self.refine_saved_draft(telegram_user_id, instruction)

    async def get_saved_draft_variants(self, telegram_user_id: int) -> dict[str, PromoDraft] | None:
        profile = await self.get_profile(telegram_user_id)
        draft = self.parse_draft(profile.last_draft_json)
        if not draft:
            return None
        return self.build_draft_variants(draft)

    async def save_current_draft_as_campaign(self, telegram_user_id: int) -> SavedPromoCampaign | None:
        profile = await self.get_profile(telegram_user_id)
        draft = self.parse_draft(profile.last_draft_json)
        if not draft:
            return None
        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        topic = self._extract_strategy_value(profile.strategy_notes, "Topic") or "Promo"
        goal = self._extract_strategy_value(profile.strategy_notes, "Goal") or "Promo"
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        campaign = SavedPromoCampaign(
            title=draft.headline[:120] or topic,
            goal=goal,
            topic=topic,
            created_at=timestamp,
            draft_json=json.dumps(asdict(draft)),
            image_json=profile.last_image_json,
        )
        campaigns.insert(0, campaign)
        profile.saved_campaigns_json = json.dumps([asdict(item) for item in campaigns[:20]])
        await self.save_profile(profile)
        return campaign

    async def list_saved_campaigns(self, telegram_user_id: int) -> list[SavedPromoCampaign]:
        profile = await self.get_profile(telegram_user_id)
        return self.parse_saved_campaigns(profile.saved_campaigns_json)

    async def list_published_campaigns(self, telegram_user_id: int) -> list[SavedPromoCampaign]:
        campaigns = await self.list_saved_campaigns(telegram_user_id)
        return [item for item in campaigns if item.status == "PUBLISHED"]

    async def list_ready_campaigns(self, telegram_user_id: int) -> list[SavedPromoCampaign]:
        campaigns = await self.list_saved_campaigns(telegram_user_id)
        return [item for item in campaigns if item.status == "READY_TO_PUBLISH"]

    async def build_image_generation_policy(
        self,
        telegram_user_id: int,
        role_keys: set[str] | None = None,
        requested_model: str | None = None,
    ) -> ImageGenerationPolicy:
        user_tier = self.resolve_image_user_tier(role_keys or set())
        monthly_limit = self.image_monthly_limit_for_tier(user_tier)
        monthly_used = await self.get_monthly_image_usage(telegram_user_id)
        global_used = await self.get_global_monthly_image_usage()
        model_order = self.image_model_order_for_tier(user_tier)
        model = self.select_allowed_image_model(user_tier, requested_model)
        fallback_models = [item for item in model_order if item != model]

        allowed = True
        message = "Image generation is ready in dry-run mode." if self.alibaba_image_dry_run else "Image generation is ready."
        if not self.alibaba_image_api_enabled:
            allowed = False
            message = "Alibaba image API is disabled. Dry-run preview only."
        elif self.alibaba_image_admin_live_only and not self.alibaba_image_dry_run and user_tier != "ADMIN":
            allowed = False
            message = "Live image generation is admin-only during safe rollout."
        elif monthly_used >= monthly_limit:
            allowed = False
            message = f"Monthly image limit reached ({monthly_used}/{monthly_limit})."
        elif global_used >= self.alibaba_global_monthly_image_cap:
            allowed = False
            message = f"Global monthly image limit reached ({global_used}/{self.alibaba_global_monthly_image_cap})."
        elif not model:
            allowed = False
            message = "Requested image model is not allowed for this user tier."

        return ImageGenerationPolicy(
            allowed=allowed,
            user_tier=user_tier,
            model=model,
            fallback_models=fallback_models,
            monthly_used=monthly_used,
            monthly_limit=monthly_limit,
            global_used=global_used,
            global_limit=self.alibaba_global_monthly_image_cap,
            dry_run=self.alibaba_image_dry_run,
            message=message,
        )

    async def build_image_generation_preview(
        self,
        telegram_user_id: int,
        role_keys: set[str] | None = None,
        requested_model: str | None = None,
    ) -> tuple[ImageGenerationPolicy, str | None]:
        profile = await self.get_profile(telegram_user_id)
        draft = self.parse_draft(profile.last_draft_json)
        policy = await self.build_image_generation_policy(telegram_user_id, role_keys, requested_model)
        if not draft:
            return policy, None
        return policy, self.build_image_prompt(profile, draft)

    async def build_image_live_preflight(
        self,
        telegram_user_id: int,
        role_keys: set[str] | None = None,
        requested_model: str | None = None,
    ) -> ImageLivePreflight:
        policy = await self.build_image_generation_policy(telegram_user_id, role_keys, requested_model)
        checks = [
            f"API enabled: {'YES' if self.alibaba_image_api_enabled else 'NO'}",
            f"Dry-run: {'ON' if self.alibaba_image_dry_run else 'OFF'}",
            f"Admin-only live rollout: {'ON' if self.alibaba_image_admin_live_only else 'OFF'}",
            f"User tier: {policy.user_tier}",
            f"Selected model: {policy.model or 'Blocked'}",
            f"Monthly usage: {policy.monthly_used}/{policy.monthly_limit}",
            f"Global usage: {policy.global_used}/{policy.global_limit}",
        ]
        blockers: list[str] = []
        if not self.alibaba_image_api_enabled:
            blockers.append("Set ALIBABA_IMAGE_API_ENABLED=true.")
        if self.alibaba_image_dry_run:
            blockers.append("Set ALIBABA_IMAGE_DRY_RUN=false for a real one-image test.")
        if not self.alibaba_image_admin_live_only:
            blockers.append("Keep ALIBABA_IMAGE_ADMIN_LIVE_ONLY=true during the first live test.")
        if policy.user_tier != "ADMIN":
            blockers.append("Use an OWNER/SUPER_ADMIN/ADMIN account for the first live test.")
        if not policy.allowed:
            blockers.append(policy.message)
        if not policy.model:
            blockers.append("No allowed image model selected.")
        return ImageLivePreflight(
            ready=not blockers,
            checks=checks,
            blockers=list(dict.fromkeys(blockers)),
        )

    async def generate_campaign_image(
        self,
        telegram_user_id: int,
        role_keys: set[str] | None = None,
        requested_model: str | None = None,
    ) -> AlibabaImageResult:
        profile = await self.get_profile(telegram_user_id)
        draft = self.parse_draft(profile.last_draft_json)
        policy = await self.build_image_generation_policy(telegram_user_id, role_keys, requested_model)
        if not draft:
            return AlibabaImageResult(False, "Generate a draft before creating an image.", [])
        prompt = self.build_image_prompt(profile, draft)
        if not policy.allowed or not policy.model:
            return AlibabaImageResult(False, policy.message, [], request=self.image_adapter.build_request(policy.model or "blocked", prompt))
        if policy.dry_run:
            return AlibabaImageResult(False, "Dry-run mode is enabled. No Alibaba quota was used.", [], request=self.image_adapter.build_request(policy.model, prompt))
        result = await self.image_adapter.generate(policy.model, prompt)
        if result.ok and result.image_urls:
            await self.record_successful_image_generation(telegram_user_id)
            await self.save_generated_image(
                telegram_user_id,
                GeneratedPromoImage(
                    model=policy.model,
                    prompt=prompt,
                    image_urls=result.image_urls,
                    created_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        return result

    async def save_generated_image(
        self,
        telegram_user_id: int,
        generated_image: GeneratedPromoImage,
    ) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.last_image_json = json.dumps(asdict(generated_image))
        return await self.save_profile(profile)

    async def get_monthly_image_usage(self, telegram_user_id: int) -> int:
        if not self.redis_client:
            return 0
        payload = await asyncio.to_thread(self.redis_client.get, self._image_usage_key(telegram_user_id))
        return self._safe_int(payload)

    async def get_global_monthly_image_usage(self) -> int:
        if not self.redis_client:
            return 0
        payload = await asyncio.to_thread(self.redis_client.get, self._global_image_usage_key())
        return self._safe_int(payload)

    async def record_successful_image_generation(self, telegram_user_id: int) -> tuple[int, int]:
        if not self.redis_client:
            return (1, 1)
        user_key = self._image_usage_key(telegram_user_id)
        global_key = self._global_image_usage_key()
        user_count = await asyncio.to_thread(self.redis_client.incr, user_key)
        global_count = await asyncio.to_thread(self.redis_client.incr, global_key)
        await asyncio.to_thread(self.redis_client.expire, user_key, 86400 * 45)
        await asyncio.to_thread(self.redis_client.expire, global_key, 86400 * 45)
        return int(user_count), int(global_count)

    async def reset_monthly_image_usage(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._image_usage_key(telegram_user_id))

    async def reset_global_monthly_image_usage(self) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._global_image_usage_key())

    async def load_saved_campaign_as_current_draft(self, telegram_user_id: int, index: int) -> PromoDraft | None:
        profile = await self.get_profile(telegram_user_id)
        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            return None
        draft = self.parse_draft(campaigns[index].draft_json)
        if not draft:
            return None
        profile.last_draft_json = campaigns[index].draft_json
        profile.last_image_json = campaigns[index].image_json
        await self.save_profile(profile)
        return draft

    async def mark_campaign_ready_to_publish(self, telegram_user_id: int, index: int) -> SavedPromoCampaign | None:
        profile = await self.get_profile(telegram_user_id)
        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            return None
        campaigns[index].status = "READY_TO_PUBLISH"
        profile.saved_campaigns_json = json.dumps([asdict(item) for item in campaigns[:20]])
        await self.save_profile(profile)
        return campaigns[index]

    async def mark_campaign_draft(self, telegram_user_id: int, index: int) -> SavedPromoCampaign | None:
        profile = await self.get_profile(telegram_user_id)
        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            return None
        campaigns[index].status = "DRAFT"
        profile.saved_campaigns_json = json.dumps([asdict(item) for item in campaigns[:20]])
        await self.save_profile(profile)
        return campaigns[index]

    async def build_campaign_publish_dry_run(self, telegram_user_id: int, index: int) -> FacebookPublishDryRun:
        profile = await self.get_profile(telegram_user_id)
        if not profile.page_id or not profile.page_access_token:
            return FacebookPublishDryRun(False, "Facebook Page ID and access token are required first.")

        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            return FacebookPublishDryRun(False, "That saved campaign is no longer available.")
        campaign = campaigns[index]
        if campaign.status != "READY_TO_PUBLISH":
            return FacebookPublishDryRun(False, "Move this campaign to READY_TO_PUBLISH before publish dry-run.")
        draft = self.parse_draft(campaign.draft_json)
        if not draft:
            return FacebookPublishDryRun(False, "The campaign draft could not be read.")

        generated_image = self.parse_generated_image(campaign.image_json)
        if generated_image and generated_image.image_urls:
            image_issue = self.validate_public_image_url(generated_image.image_urls[0])
            if image_issue:
                return FacebookPublishDryRun(False, f"Saved image URL is not publish-ready: {image_issue}")
        request = self.build_page_publish_request(profile, draft, generated_image)
        if not request:
            return FacebookPublishDryRun(False, "Could not build the Facebook publish request.")
        return FacebookPublishDryRun(True, "Dry-run publish request is ready.", request)

    async def build_access_validation_dry_run(self, telegram_user_id: int) -> FacebookPublishDryRun:
        profile = await self.get_profile(telegram_user_id)
        if not profile.page_id or not profile.page_access_token:
            return FacebookPublishDryRun(False, "Save Facebook Page ID and access token first.")
        request = self.build_page_validation_request(profile)
        if not request:
            return FacebookPublishDryRun(False, "Could not build the Facebook validation request.")
        return FacebookPublishDryRun(True, "Dry-run validation request is ready.", request)

    async def build_publish_safety_status(self, telegram_user_id: int) -> FacebookPublishSafetyStatus:
        profile = await self.get_profile(telegram_user_id)
        readiness = self.build_access_readiness(profile)
        checks = [
            f"Graph API enabled: {'YES' if self.graph_api_enabled else 'NO'}",
            f"Graph version: {self.graph_version}",
            f"Page ID saved: {'YES' if readiness.page_id_saved else 'NO'}",
            f"Access token saved: {'YES' if readiness.token_saved else 'NO'}",
            f"Access token preview: {readiness.token_preview}",
        ]
        blockers: list[str] = []
        if not self.graph_api_enabled:
            blockers.append("Set FACEBOOK_PROMO_GRAPH_API_ENABLED=true before live Facebook posting.")
        blockers.extend(readiness.issues)
        return FacebookPublishSafetyStatus(
            live_enabled=self.graph_api_enabled,
            graph_version=self.graph_version,
            access_ready=readiness.ready,
            checks=checks,
            blockers=list(dict.fromkeys(blockers)),
        )

    async def build_campaign_publish_checklist(self, telegram_user_id: int, index: int) -> FacebookCampaignPublishChecklist:
        profile = await self.get_profile(telegram_user_id)
        readiness = self.build_access_readiness(profile)
        checks = [
            f"Facebook access: {'ready' if readiness.ready else 'needs setup'}",
            f"Graph live posting: {'enabled' if self.graph_api_enabled else 'disabled'}",
        ]
        blockers = [*readiness.issues]
        publish_type = "text post"

        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            blockers.append("Saved campaign is no longer available.")
            return FacebookCampaignPublishChecklist(False, publish_type, checks, list(dict.fromkeys(blockers)))

        campaign = campaigns[index]
        if campaign.status != "READY_TO_PUBLISH":
            blockers.append("Campaign is not marked ready to publish.")

        draft = self.parse_draft(campaign.draft_json)
        if draft:
            checks.append("Draft: readable")
        else:
            blockers.append("Campaign draft could not be read.")

        generated_image = self.parse_generated_image(campaign.image_json)
        if generated_image and generated_image.image_urls:
            publish_type = "photo post"
            image_issue = self.validate_public_image_url(generated_image.image_urls[0])
            if image_issue:
                blockers.append(f"Image URL issue: {image_issue}")
            else:
                checks.append("Image URL: public HTTPS format")
        else:
            checks.append("Image: not attached; text-only publish")

        if not self.graph_api_enabled:
            blockers.append("Graph live posting is disabled; use dry-run only.")

        return FacebookCampaignPublishChecklist(
            live_ready=not blockers,
            publish_type=publish_type,
            checks=checks,
            blockers=list(dict.fromkeys(blockers)),
        )

    async def validate_page_access(self, telegram_user_id: int) -> FacebookGraphResponse:
        profile = await self.get_profile(telegram_user_id)
        request_preview = self.build_page_validation_request(profile, self.graph_version)
        if not request_preview or not profile.page_access_token:
            return FacebookGraphResponse(False, None, "Save Facebook Page ID and access token first.")
        return await self.graph_adapter.execute(request_preview, profile.page_access_token)

    async def publish_campaign(self, telegram_user_id: int, index: int) -> FacebookGraphResponse:
        profile = await self.get_profile(telegram_user_id)
        if not profile.page_access_token:
            return FacebookGraphResponse(False, None, "Save Facebook Page access token first.")
        dry_run = await self.build_campaign_publish_dry_run(telegram_user_id, index)
        if not dry_run.ok or not dry_run.request:
            return FacebookGraphResponse(False, None, dry_run.message)
        result = await self.graph_adapter.execute(dry_run.request, profile.page_access_token)
        if result.ok:
            await self.mark_campaign_published(telegram_user_id, index, result)
        return result

    async def mark_campaign_published(
        self,
        telegram_user_id: int,
        index: int,
        result: FacebookGraphResponse,
    ) -> SavedPromoCampaign | None:
        profile = await self.get_profile(telegram_user_id)
        campaigns = self.parse_saved_campaigns(profile.saved_campaigns_json)
        if index < 0 or index >= len(campaigns):
            return None
        campaigns[index].status = "PUBLISHED"
        campaigns[index].published_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        campaigns[index].publish_response_json = result.body
        campaigns[index].facebook_post_id = self.extract_facebook_post_id(result.body)
        profile.saved_campaigns_json = json.dumps([asdict(item) for item in campaigns[:20]])
        await self.save_profile(profile)
        return campaigns[index]

    async def set_page_id(self, telegram_user_id: int, page_id: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.page_id = self.normalize_page_id(page_id)
        return await self.save_profile(profile)

    async def set_page_access_token(self, telegram_user_id: int, access_token: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.page_access_token = access_token.strip()
        return await self.save_profile(profile)

    async def set_brand_notes(self, telegram_user_id: int, notes: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.brand_notes = notes.strip()
        return await self.save_profile(profile)

    async def set_preference(self, telegram_user_id: int, key: str, value: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        if key == "tone":
            profile.preferred_tone = value
        elif key == "emoji":
            profile.preferred_emoji_style = value
        elif key == "cta":
            profile.preferred_cta_style = value
        elif key == "image":
            profile.preferred_image_style = value
        return await self.save_profile(profile)

    async def update_strategy(self, telegram_user_id: int, instruction: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        normalized = instruction.strip()
        profile.last_goal = normalized
        profile.strategy_notes = normalized if not profile.strategy_notes else f"{profile.strategy_notes}\n- {normalized}"
        return await self.save_profile(profile)

    async def set_status(self, telegram_user_id: int, status: str) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.status = "ACTIVE" if status.upper() == "ACTIVE" else "INACTIVE"
        return await self.save_profile(profile)

    async def clear_access(self, telegram_user_id: int) -> FacebookPromoProfile:
        profile = await self.get_profile(telegram_user_id)
        profile.page_id = None
        profile.page_access_token = None
        return await self.save_profile(profile)

    @staticmethod
    def mask_token(token: str | None) -> str:
        if not token:
            return "Not connected"
        if len(token) <= 10:
            return "Saved"
        return f"{token[:4]}...{token[-4:]}"

    @staticmethod
    def normalize_page_id(page_id: str) -> str:
        value = page_id.strip()
        if not value:
            return ""
        parsed = parse.urlparse(value if "://" in value else f"https://{value}")
        if parsed.netloc and "facebook.com" in parsed.netloc:
            path_parts = [part for part in parsed.path.split("/") if part]
            if path_parts and path_parts[0].lower() in {"pages", "profile.php"} and len(path_parts) > 1:
                return path_parts[-1].strip()
            if path_parts:
                return path_parts[0].strip()
        return value

    @classmethod
    def build_access_readiness(cls, profile: FacebookPromoProfile) -> FacebookAccessReadiness:
        issues: list[str] = []
        page_id = (profile.page_id or "").strip()
        token = (profile.page_access_token or "").strip()
        if not page_id:
            issues.append("Page ID is missing.")
        elif any(char.isspace() for char in page_id):
            issues.append("Page ID should not contain spaces.")
        if not token:
            issues.append("Page access token is missing.")
        elif len(token) < 20:
            issues.append("Access token looks too short. Paste the full Page access token.")
        elif any(char.isspace() for char in token):
            issues.append("Access token should not contain spaces or line breaks.")

        if not page_id:
            next_step = "Save Page ID first."
        elif not token:
            next_step = "Save Page access token next."
        elif issues:
            next_step = "Fix the access issue above, then run Dry Run Validate."
        else:
            next_step = "Run Dry Run Validate first. Use live Validate only when Graph API is enabled."

        return FacebookAccessReadiness(
            ready=not issues,
            page_id_saved=bool(page_id),
            token_saved=bool(token),
            token_preview=cls.mask_token(token),
            issues=issues,
            next_step=next_step,
        )

    @staticmethod
    def build_page_validation_request(
        profile: FacebookPromoProfile,
        graph_version: str = "v24.0",
    ) -> FacebookGraphRequest | None:
        if not profile.page_id or not profile.page_access_token:
            return None
        return FacebookGraphRequest(
            method="GET",
            url=f"https://graph.facebook.com/{graph_version.strip('/')}/{profile.page_id}",
            headers={"Authorization": "Bearer <PAGE_ACCESS_TOKEN>"},
            payload={"fields": "id,name"},
        )

    @staticmethod
    def build_page_feed_publish_request(
        profile: FacebookPromoProfile,
        draft: PromoDraft,
        graph_version: str = "v24.0",
    ) -> FacebookGraphRequest | None:
        if not profile.page_id or not profile.page_access_token:
            return None
        return FacebookGraphRequest(
            method="POST",
            url=f"https://graph.facebook.com/{graph_version.strip('/')}/{profile.page_id}/feed",
            headers={"Authorization": "Bearer <PAGE_ACCESS_TOKEN>"},
            payload={"message": FacebookPromoAIService.build_publish_message(draft)},
        )

    @staticmethod
    def build_page_photo_publish_request(
        profile: FacebookPromoProfile,
        draft: PromoDraft,
        generated_image: GeneratedPromoImage,
        graph_version: str = "v24.0",
    ) -> FacebookGraphRequest | None:
        if not profile.page_id or not profile.page_access_token or not generated_image.image_urls:
            return None
        if FacebookPromoAIService.validate_public_image_url(generated_image.image_urls[0]):
            return None
        return FacebookGraphRequest(
            method="POST",
            url=f"https://graph.facebook.com/{graph_version.strip('/')}/{profile.page_id}/photos",
            headers={"Authorization": "Bearer <PAGE_ACCESS_TOKEN>"},
            payload={
                "url": generated_image.image_urls[0],
                "caption": FacebookPromoAIService.build_publish_message(draft),
            },
        )

    @staticmethod
    def build_page_publish_request(
        profile: FacebookPromoProfile,
        draft: PromoDraft,
        generated_image: GeneratedPromoImage | None = None,
        graph_version: str = "v24.0",
    ) -> FacebookGraphRequest | None:
        if generated_image and generated_image.image_urls:
            return FacebookPromoAIService.build_page_photo_publish_request(
                profile,
                draft,
                generated_image,
                graph_version,
            )
        return FacebookPromoAIService.build_page_feed_publish_request(profile, draft, graph_version)

    @staticmethod
    def validate_public_image_url(image_url: str | None) -> str | None:
        if not image_url or not image_url.strip():
            return "image URL is missing."
        parsed = parse.urlparse(image_url.strip())
        if parsed.scheme.lower() != "https":
            return "Facebook photo publishing needs a public HTTPS image URL."
        if not parsed.netloc:
            return "image URL host is missing."
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return "image URL host is missing."
        if hostname in {"localhost"} or hostname.endswith(".local"):
            return "image URL must be public, not localhost or .local."
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            return None
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return "image URL must not point to a private or reserved IP address."
        return None

    @staticmethod
    def build_publish_message(draft: PromoDraft) -> str:
        parts = [
            draft.headline.strip(),
            draft.primary_copy.strip(),
            draft.cta.strip(),
            draft.hashtags.strip(),
        ]
        return "\n\n".join(part for part in parts if part)[:5000]

    @staticmethod
    def extract_facebook_post_id(body: str | None) -> str | None:
        if not body:
            return None
        try:
            payload = json.loads(body)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        post_id = payload.get("id") or payload.get("post_id")
        return str(post_id) if post_id else None

    @staticmethod
    def is_ready(profile: FacebookPromoProfile) -> bool:
        return bool(profile.page_id and profile.page_access_token and (profile.brand_notes or profile.strategy_notes))

    @staticmethod
    def generate_recommendations(pending: PendingFacebookPromoAction) -> list[PromoRecommendation]:
        topic = pending.topic or "your product"
        audience = pending.audience or "your audience"
        image_hint = "with image support" if pending.image_mode == "NEEDED" else "as text-first copy"

        if pending.goal_key == "SALE":
            return [
                PromoRecommendation("PREMIUM_VALUE", "Premium value angle", f"Position {topic} as high-value and trustworthy for {audience}, {image_hint}."),
                PromoRecommendation("OFFER_PUSH", "Offer push angle", f"Lead with urgency, discount, and CTA so {audience} feels a reason to act now."),
                PromoRecommendation("PROBLEM_SOLUTION", "Problem-solution angle", f"Show the pain point first, then present {topic} as the smart answer."),
            ]
        if pending.goal_key == "ENGAGEMENT":
            return [
                PromoRecommendation("QUESTION_HOOK", "Question hook", f"Use a light question-led post so {audience} wants to comment before buying."),
                PromoRecommendation("LIFESTYLE_STORY", "Lifestyle story", f"Make {topic} feel relatable through a short story-driven post."),
                PromoRecommendation("CHOICE_POST", "Choice post", f"Turn the promo into a simple pick-one interaction to boost reach and replies."),
            ]
        if pending.goal_key == "OFFER":
            return [
                PromoRecommendation("COUNTDOWN", "Countdown angle", f"Frame the offer as limited-time with a strong action push for {audience}."),
                PromoRecommendation("BUNDLE_VALUE", "Bundle value angle", f"Highlight extra value, combo benefits, or savings around {topic}."),
                PromoRecommendation("DIRECT_CTA", "Direct CTA angle", f"Keep it clear and fast: offer, benefit, deadline, and what to do next."),
            ]
        if pending.goal_key == "BRAND":
            return [
                PromoRecommendation("TRUST_BUILD", "Trust-building angle", f"Show why {topic} feels dependable and polished for {audience}."),
                PromoRecommendation("BRAND_PERSONALITY", "Brand personality angle", f"Make the post memorable by showing the brand tone behind {topic}."),
                PromoRecommendation("SIGNATURE_LOOK", "Signature look angle", f"Focus on a premium visual identity and distinctive message for recall."),
            ]
        return [
            PromoRecommendation("SMART_PROMO", "Smart promo angle", f"Balance product value, audience fit, and CTA around {topic}."),
            PromoRecommendation("SOFT_SELL", "Soft-sell angle", f"Make it useful and attractive first, then guide {audience} toward action."),
            PromoRecommendation("BOLD_SALE", "Bold sale angle", f"Make the offer more direct and conversion-focused for fast attention."),
        ]

    @staticmethod
    def generate_strategy_plan(pending: PendingFacebookPromoAction) -> PromoStrategyPlan:
        angle_map = {item.key: item.title for item in FacebookPromoAIService.generate_recommendations(pending)}
        angle_title = angle_map.get(pending.selected_angle or "", pending.selected_angle or "Chosen angle")
        topic = pending.topic or "your product"
        audience = pending.audience or "your audience"
        feedback_suffix = f" Extra note: {pending.plan_feedback}." if pending.plan_feedback else ""

        if pending.selected_angle == "PREMIUM_VALUE":
            return PromoStrategyPlan(
                angle_title=angle_title,
                positioning=f"Present {topic} as premium, polished, and worth the price for {audience}.{feedback_suffix}",
                hook_style="Open with desirability, quality, or confidence instead of discount-first language.",
                copy_direction="Use concise, trust-building lines that make the product feel elegant and high-value.",
                cta_direction="Invite the audience to message, order, or explore now without sounding desperate.",
                image_direction="Use a clean premium visual with product focus, calm background, and luxury feel.",
            )
        if pending.selected_angle == "OFFER_PUSH":
            return PromoStrategyPlan(
                angle_title=angle_title,
                positioning=f"Lead with the strongest offer reason for {audience} to act on {topic} now.{feedback_suffix}",
                hook_style="Start with urgency, benefit, or limited-time value in the first line.",
                copy_direction="Keep the copy fast, clear, and conversion-heavy with visible value and low friction.",
                cta_direction="Use direct action language like order now, inbox now, or claim today's offer.",
                image_direction="Use bold promo styling with price, offer emphasis, and high attention contrast.",
            )
        if pending.selected_angle == "QUESTION_HOOK":
            return PromoStrategyPlan(
                angle_title=angle_title,
                positioning=f"Make {topic} feel relatable and conversation-worthy for {audience}.{feedback_suffix}",
                hook_style="Open with a light question or choice that encourages comments.",
                copy_direction="Keep it human, simple, and engagement-first before moving into promotion.",
                cta_direction="Ask for reactions, comments, or preference before pushing a hard sale.",
                image_direction="Use a lifestyle-friendly visual that feels social and easy to react to.",
            )
        return PromoStrategyPlan(
            angle_title=angle_title,
            positioning=f"Balance attention, value, and conversion around {topic} for {audience}.{feedback_suffix}",
            hook_style="Start with the strongest practical or emotional reason to care.",
            copy_direction="Write clear benefit-led copy with one strong message instead of too many claims.",
            cta_direction="Guide the audience toward one clear next step only.",
            image_direction="Use a clean promo visual that matches the product and post goal.",
        )

    @staticmethod
    def generate_draft(profile: FacebookPromoProfile, plan: PromoStrategyPlan) -> PromoDraft:
        topic = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Topic") or "your product"
        audience = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Audience") or "your audience"
        goal = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Goal") or "Promo"
        image_mode = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Image mode") or "AUTO"
        resolved = FacebookPromoAIService.resolve_preferences(profile)
        tone = resolved["tone"]
        emoji_style = resolved["emoji"]
        cta_style = resolved["cta"]
        image_style = resolved["image"]

        headline = f"{topic} for {audience}".replace("your ", "").strip()
        if tone == "premium":
            headline = f"Premium {headline}"
        elif tone == "friendly":
            headline = f"{headline} made simple"
        elif tone == "bold":
            headline = f"{headline} you should not miss"

        voice_line = "Keep the voice balanced and easy to trust."
        if tone == "premium":
            voice_line = "Keep the voice polished, elegant, and high-value."
        elif tone == "friendly":
            voice_line = "Keep the voice warm, clear, and easy to relate to."
        elif tone == "bold":
            voice_line = "Keep the voice confident, energetic, and conversion-focused."

        primary_copy = (
            f"{headline}.\n\n"
            f"{plan.positioning} {plan.copy_direction} "
            f"This version is designed around the goal of {goal.lower()} while keeping the message clear and audience-fit. "
            f"{voice_line}"
        )
        short_copy = f"{headline}. {plan.cta_direction}"
        cta = plan.cta_direction
        if cta_style == "soft":
            cta = "Send a message if you want details, pricing, or help choosing the right option."
        elif cta_style == "comment":
            cta = "Comment or send a message now and we will help you with the next step."
        elif cta_style == "inbox":
            cta = "Inbox now to order, check price, or reserve yours today."
        hashtags = FacebookPromoAIService._build_hashtags(topic, audience)
        if emoji_style == "none":
            hashtags = hashtags.replace("#SmartPromo", "#BrandPost")
        elif emoji_style == "playful":
            short_copy = f"{short_copy.rstrip('. ')} ✨"
            cta = f"{cta.rstrip('. ')} 🚀"
        image_concept = (
            f"{plan.image_direction} "
            f"Image mode preference: {image_mode}. "
            f"Make it feel aligned with {topic} and attractive for {audience}."
        )
        if image_style == "premium":
            image_concept = f"Premium visual direction. {image_concept}"
        elif image_style == "minimal":
            image_concept = f"Minimal clean visual direction. {image_concept}"
        elif image_style == "lifestyle":
            image_concept = f"Lifestyle visual direction. {image_concept}"
        elif image_style == "sale":
            image_concept = f"Sale-focused visual direction. {image_concept}"
        return PromoDraft(
            headline=headline[:120],
            primary_copy=primary_copy[:900],
            short_copy=short_copy[:260],
            cta=cta[:220],
            hashtags=hashtags[:220],
            image_concept=image_concept[:500],
        )

    @staticmethod
    def build_gemini_draft_prompt(profile: FacebookPromoProfile, plan: PromoStrategyPlan) -> str:
        topic = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Topic") or "your product"
        audience = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Audience") or "your audience"
        goal = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Goal") or "Promo"
        user_request = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "User request") or ""
        preferences = FacebookPromoAIService.describe_preferences(profile)
        brand_notes = (profile.brand_notes or "Not provided").strip()
        strategy_notes = (profile.strategy_notes or "Not provided").strip()
        return (
            "You are Facebook Promo AI for a small business owner. "
            "Write one high-converting but natural Facebook promo draft. "
            "Ask no follow-up questions in this response because the strategy has already been chosen. "
            "Return ONLY valid JSON with these exact string keys: "
            "headline, primary_copy, short_copy, cta, hashtags, image_concept.\n\n"
            f"Goal: {goal}\n"
            f"Topic/product: {topic}\n"
            f"Audience: {audience}\n"
            f"Original user request: {user_request}\n"
            f"Brand notes: {brand_notes[:900]}\n"
            f"Strategy memory: {strategy_notes[:1200]}\n\n"
            "Chosen plan:\n"
            f"- Angle: {plan.angle_title}\n"
            f"- Positioning: {plan.positioning}\n"
            f"- Hook style: {plan.hook_style}\n"
            f"- Copy direction: {plan.copy_direction}\n"
            f"- CTA direction: {plan.cta_direction}\n"
            f"- Image direction: {plan.image_direction}\n\n"
            "Style preferences:\n"
            f"- Tone: {preferences['tone']}\n"
            f"- Emoji: {preferences['emoji']}\n"
            f"- CTA: {preferences['cta']}\n"
            f"- Image: {preferences['image']}\n\n"
            "Rules: primary_copy should be 2-5 short paragraphs, clear and sellable. "
            "short_copy should be one compact version. "
            "hashtags should be relevant and not spammy. "
            "image_concept should be a practical prompt idea for a generated promo visual."
        )

    @staticmethod
    def build_image_prompt(profile: FacebookPromoProfile, draft: PromoDraft) -> str:
        topic = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Topic") or draft.headline
        audience = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Audience") or "target customers"
        goal = FacebookPromoAIService._extract_strategy_value(profile.strategy_notes, "Goal") or "Facebook promotion"
        brand_notes = (profile.brand_notes or "clean trustworthy small business brand").strip()
        preferences = FacebookPromoAIService.describe_preferences(profile)
        prompt = (
            f"Create a square Facebook promotional image for {topic}. "
            f"Goal: {goal}. Target audience: {audience}. "
            f"Visual direction: {draft.image_concept}. "
            f"Brand style: {brand_notes[:350]}. "
            f"Tone: {preferences['tone']}. Image style: {preferences['image']}. "
            "Use a clean product-focused composition, readable ad layout, realistic lighting, "
            "professional ecommerce look, no messy background, no distorted hands or faces. "
            f"Optional short text on image: {draft.headline[:80]}."
        )
        return " ".join(prompt.split())[:1200]

    @staticmethod
    def parse_plan(payload: str | None) -> PromoStrategyPlan | None:
        if not payload:
            return None
        try:
            return PromoStrategyPlan(**json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def parse_draft(payload: str | None) -> PromoDraft | None:
        if not payload:
            return None
        try:
            return PromoDraft(**json.loads(payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def parse_generated_image(payload: str | None) -> GeneratedPromoImage | None:
        if not payload:
            return None
        try:
            data = json.loads(payload)
            return GeneratedPromoImage(
                model=str(data["model"]),
                prompt=str(data["prompt"]),
                image_urls=[str(item) for item in data.get("image_urls", [])],
                created_at=str(data["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def parse_ai_draft_payload(payload: str | None) -> PromoDraft | None:
        if not payload:
            return None
        normalized = payload.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.lower().startswith("json"):
                normalized = normalized[4:].strip()
        try:
            data = json.loads(normalized)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        required = ["headline", "primary_copy", "short_copy", "cta", "hashtags", "image_concept"]
        if not all(str(data.get(key, "")).strip() for key in required):
            return None
        return PromoDraft(
            headline=str(data["headline"]).strip()[:120],
            primary_copy=str(data["primary_copy"]).strip()[:900],
            short_copy=str(data["short_copy"]).strip()[:260],
            cta=str(data["cta"]).strip()[:220],
            hashtags=str(data["hashtags"]).strip()[:220],
            image_concept=str(data["image_concept"]).strip()[:500],
        )

    @staticmethod
    def parse_saved_campaigns(payload: str | None) -> list[SavedPromoCampaign]:
        if not payload:
            return []
        try:
            campaigns = []
            for item in json.loads(payload):
                allowed = {
                    field: item.get(field)
                    for field in SavedPromoCampaign.__dataclass_fields__
                }
                campaigns.append(SavedPromoCampaign(**allowed))
            return campaigns
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def refine_draft(draft: PromoDraft, instruction: str) -> PromoDraft:
        normalized = instruction.strip().lower()
        headline = draft.headline
        primary_copy = draft.primary_copy
        short_copy = draft.short_copy
        cta = draft.cta
        hashtags = draft.hashtags
        image_concept = draft.image_concept

        if "short" in normalized:
            primary_copy = primary_copy[:420].rstrip(". ") + "."
            short_copy = short_copy[:180].rstrip(". ") + "."
        if "premium" in normalized or "luxury" in normalized:
            headline = f"Premium {headline}"[:120]
            primary_copy = primary_copy.replace("clear and audience-fit", "polished, premium, and audience-fit")
            image_concept = f"Premium style. {image_concept}"[:500]
        if "urgent" in normalized or "cta" in normalized or "action" in normalized:
            cta = "Send a message now to get the best offer before it ends."[:220]
            short_copy = f"{short_copy.rstrip('. ')} {cta}"[:260]
        if "less emoji" in normalized or "no emoji" in normalized:
            hashtags = hashtags.replace("#SmartPromo", "#BrandPost")
        if "friendly" in normalized or "soft" in normalized:
            primary_copy = primary_copy.replace("stronger", "warmer").replace("clear", "friendly")
            cta = "Send a message if you want details or want to order."[:220]
        if "bangla" in normalized:
            headline = f"{headline} | Bangla-friendly"[:120]
            short_copy = f"{short_copy.rstrip('. ')} Inbox now for details."[:260]
        if "minimal" in normalized:
            image_concept = f"Minimal clean style. {image_concept}".replace("Premium style. ", "")[:500]
        if "lifestyle" in normalized:
            image_concept = f"Lifestyle visual style. {image_concept}"[:500]
        if "sale visual" in normalized or "sale-focused" in normalized:
            image_concept = f"Bold sale-focused visual. {image_concept}"[:500]

        return PromoDraft(
            headline=headline[:120],
            primary_copy=primary_copy[:900],
            short_copy=short_copy[:260],
            cta=cta[:220],
            hashtags=hashtags[:220],
            image_concept=image_concept[:500],
        )

    @staticmethod
    def build_draft_variants(draft: PromoDraft) -> dict[str, PromoDraft]:
        return {
            "Base": draft,
            "Premium": FacebookPromoAIService.refine_draft(draft, "make it more premium"),
            "Short": FacebookPromoAIService.refine_draft(draft, "make it shorter"),
            "Urgent": FacebookPromoAIService.refine_draft(draft, "make it more urgent with stronger CTA"),
        }

    @staticmethod
    def _extract_strategy_value(strategy_notes: str | None, key: str) -> str | None:
        if not strategy_notes:
            return None
        prefix = f"{key}: "
        for line in strategy_notes.splitlines():
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()
        return None

    @staticmethod
    def _build_hashtags(topic: str, audience: str) -> str:
        topic_word = "".join(ch for ch in topic.title() if ch.isalnum()) or "Promo"
        audience_word = "".join(ch for ch in audience.title() if ch.isalnum()) or "Audience"
        return f"#{topic_word} #{audience_word} #FacebookPromo #ShopNow #SmartPromo"

    @staticmethod
    def describe_preferences(profile: FacebookPromoProfile) -> dict[str, str]:
        resolved = FacebookPromoAIService.resolve_preferences(profile)
        explicit = {
            "tone": profile.preferred_tone,
            "emoji": profile.preferred_emoji_style,
            "cta": profile.preferred_cta_style,
            "image": profile.preferred_image_style,
        }
        described: dict[str, str] = {}
        for key, value in resolved.items():
            if explicit.get(key):
                described[key] = value
            else:
                described[key] = f"{value} (learned)" if value != FacebookPromoAIService.default_preferences()[key] else value
        return described

    @staticmethod
    def default_preferences() -> dict[str, str]:
        return {
            "tone": "balanced",
            "emoji": "light",
            "cta": "direct",
            "image": "brand-fit",
        }

    @staticmethod
    def resolve_preferences(profile: FacebookPromoProfile) -> dict[str, str]:
        defaults = FacebookPromoAIService.default_preferences()
        learned = FacebookPromoAIService.infer_preferences_from_campaigns(
            FacebookPromoAIService.parse_saved_campaigns(profile.saved_campaigns_json)
        )
        return {
            "tone": profile.preferred_tone or learned["tone"] or defaults["tone"],
            "emoji": profile.preferred_emoji_style or learned["emoji"] or defaults["emoji"],
            "cta": profile.preferred_cta_style or learned["cta"] or defaults["cta"],
            "image": profile.preferred_image_style or learned["image"] or defaults["image"],
        }

    @staticmethod
    def infer_preferences_from_campaigns(campaigns: list[SavedPromoCampaign]) -> dict[str, str | None]:
        learned: dict[str, str | None] = {"tone": None, "emoji": None, "cta": None, "image": None}
        approved = [item for item in campaigns if item.status == "READY_TO_PUBLISH"]
        if not approved:
            return learned

        for campaign in approved:
            draft = FacebookPromoAIService.parse_draft(campaign.draft_json)
            if not draft:
                continue
            headline = draft.headline.lower()
            cta = draft.cta.lower()
            image_concept = draft.image_concept.lower()
            short_copy = draft.short_copy

            if not learned["tone"]:
                if "premium" in headline or "luxury" in image_concept:
                    learned["tone"] = "premium"
                elif "made simple" in headline or "warm" in cta:
                    learned["tone"] = "friendly"
                elif "should not miss" in headline or "best offer before it ends" in cta:
                    learned["tone"] = "bold"

            if not learned["emoji"]:
                if "✨" in short_copy or "🚀" in draft.cta:
                    learned["emoji"] = "playful"
                elif "#BrandPost" in draft.hashtags:
                    learned["emoji"] = "none"

            if not learned["cta"]:
                if "inbox now" in cta:
                    learned["cta"] = "inbox"
                elif "comment or send a message" in cta:
                    learned["cta"] = "comment"
                elif "if you want details" in cta:
                    learned["cta"] = "soft"

            if not learned["image"]:
                if "minimal" in image_concept:
                    learned["image"] = "minimal"
                elif "lifestyle" in image_concept:
                    learned["image"] = "lifestyle"
                elif "sale-focused" in image_concept or "bold sale" in image_concept:
                    learned["image"] = "sale"
                elif "premium visual" in image_concept or "luxury" in image_concept:
                    learned["image"] = "premium"

        return learned

    @staticmethod
    def ready_campaign_index_items(campaigns: list[SavedPromoCampaign]) -> list[tuple[int, str]]:
        return [
            (index, item.title)
            for index, item in enumerate(campaigns)
            if item.status == "READY_TO_PUBLISH"
        ]

    @staticmethod
    def published_campaign_index_items(campaigns: list[SavedPromoCampaign]) -> list[tuple[int, str]]:
        return [
            (index, item.title)
            for index, item in enumerate(campaigns)
            if item.status == "PUBLISHED"
        ]

    @classmethod
    def resolve_image_user_tier(cls, role_keys: set[str]) -> str:
        normalized = {item.upper() for item in role_keys}
        if normalized & {"OWNER", "SUPER_ADMIN", "ADMIN"}:
            return "ADMIN"
        if normalized & {"PAID", "PAID_USER", "PREMIUM", "SUBSCRIBER"}:
            return "PAID"
        return "FREE"

    def image_monthly_limit_for_tier(self, user_tier: str) -> int:
        if user_tier == "FREE":
            return self.alibaba_free_monthly_image_cap
        return self.alibaba_paid_monthly_image_cap

    @classmethod
    def image_model_order_for_tier(cls, user_tier: str) -> list[str]:
        if user_tier == "FREE":
            return [*cls.FREE_IMAGE_MODELS]
        if user_tier == "ADMIN":
            return [*cls.ADMIN_IMAGE_MODELS]
        return [*cls.PAID_IMAGE_MODELS]

    @classmethod
    def select_allowed_image_model(cls, user_tier: str, requested_model: str | None = None) -> str | None:
        allowed = cls.image_model_order_for_tier(user_tier)
        if not requested_model:
            return allowed[0] if allowed else None
        normalized = requested_model.strip()
        if user_tier == "FREE" and normalized in cls.PREMIUM_IMAGE_MODELS:
            return None
        return normalized if normalized in allowed else None

    @staticmethod
    def image_model_rankings() -> list[tuple[int, str, str]]:
        return [
            (1, "qwen-image-max", "Premium highest-quality image generation"),
            (2, "qwen-image-2.0-pro", "Strong modern image generation"),
            (3, "wan2.7-image-pro", "High-quality Wan image generation"),
            (4, "qwen-image-plus", "Good general image generation"),
            (5, "qwen-image-2.0", "Balanced paid/default image generation"),
            (6, "wan2.7-image", "Allowed fallback image generation"),
            (7, "qwen-image-edit-max", "Premium image editing only"),
            (8, "qwen-image-edit-plus", "Image editing only"),
            (9, "qwen-image-edit", "Basic image editing only"),
            (10, "z-image-turbo", "Free-tier fast/basic image generation"),
        ]

    @staticmethod
    def _safe_int(payload: object) -> int:
        if payload is None:
            return 0
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        try:
            return int(payload)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _image_usage_month() -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    @classmethod
    def _image_usage_key(cls, telegram_user_id: int) -> str:
        return f"em:facebook_promo:image_usage:{telegram_user_id}:{cls._image_usage_month()}"

    @classmethod
    def _global_image_usage_key(cls) -> str:
        return f"em:facebook_promo:image_usage:global:{cls._image_usage_month()}"

    @staticmethod
    def _profile_key(telegram_user_id: int) -> str:
        return f"em:facebook_promo:profile:{telegram_user_id}"

    @staticmethod
    def _pending_key(telegram_user_id: int) -> str:
        return f"em:facebook_promo:pending:{telegram_user_id}"
