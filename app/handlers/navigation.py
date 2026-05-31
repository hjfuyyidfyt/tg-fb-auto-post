from __future__ import annotations

import asyncio
import calendar
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ChatMemberUpdated, ChatPermissions, Message

from app.core.runtime import AppContext
from app.db.redis_client import build_redis_client
from app.keyboards.main_menu import (
    MAIN_MENU_KEYS,
    MAIN_MENU_LABELS,
    build_main_menu_keyboard,
    normalize_main_menu_label,
)
from app.keyboards.section_actions import (
    build_facebook_promo_access_keyboard,
    build_facebook_promo_access_v2_keyboard,
    build_facebook_promo_ai_ready_keyboard,
    build_facebook_promo_ai_hub_v2_keyboard,
    build_facebook_promo_ai_hub_v3_keyboard,
    build_facebook_promo_simple_keyboard,
    build_facebook_promo_brief_keyboard,
    build_facebook_promo_campaigns_v2_keyboard,
    build_facebook_promo_campaign_detail_keyboard,
    build_facebook_promo_draft_keyboard,
    build_facebook_promo_draft_v2_keyboard,
    build_facebook_promo_draft_v4_keyboard,
    build_facebook_promo_goal_keyboard,
    build_facebook_promo_image_keyboard,
    build_facebook_promo_image_preview_keyboard,
    build_facebook_promo_plan_keyboard,
    build_facebook_promo_preferences_keyboard,
    build_facebook_promo_published_campaign_detail_keyboard,
    build_facebook_promo_published_history_keyboard,
    build_facebook_promo_publish_confirm_keyboard,
    build_facebook_promo_ready_campaign_detail_keyboard,
    build_facebook_promo_ready_queue_keyboard,
    build_facebook_promo_recommendation_keyboard,
    build_onboarding_keyboard,
    build_empty_recovery_keyboard,
    build_review_hub_keyboard,
    build_search_recovery_keyboard,
    build_automation_rule_detail_keyboard,
    build_automation_rules_keyboard,
    build_automation_template_keyboard,
    build_bot_detail_keyboard,
    build_bot_configs_keyboard,
    build_bot_logs_keyboard,
    build_bot_status_keyboard,
    build_broadcast_select_keyboard,
    build_group_control_keyboard,
    build_group_filter_control_keyboard,
    build_group_filter_keyboard,
    build_group_moderation_keyboard,
    build_group_welcome_control_keyboard,
    build_group_welcome_keyboard,
    build_group_warning_control_keyboard,
    build_group_warning_keyboard,
    build_entity_list_keyboard,
    build_pending_entities_keyboard,
    build_post_confirm_keyboard,
    build_schedule_mode_keyboard,
    SECTION_ACTIONS,
    build_channel_post_keyboard,
    build_channel_schedule_keyboard,
    build_entity_review_keyboard,
    build_schedule_list_keyboard,
    build_schedule_confirm_keyboard,
    build_schedule_monthday_keyboard,
    build_schedule_time_shortcuts_keyboard,
    build_schedule_weekday_keyboard,
    build_section_actions_keyboard,
    build_success_next_keyboard,
    build_bot_picker_keyboard,
)
from app.services.access import AccessService
from app.services.automation import AutomationService
from app.services.bots import ManagedBotService
from app.services.auth import (
    can_access_admin_ui,
    can_open_section,
    can_run_section_action,
    get_visible_main_menu_keys,
    is_owner,
)
from app.services.entities import ManagedEntityService
from app.services.group_events import GroupEventService
from app.services.intent_utils import build_intent_fallback_text, parse_natural_intent
from app.services.media_utils import (
    MEDIA_ONLY_SENTINEL,
    describe_incoming_media,
    extract_message_text,
    message_has_supported_media,
    send_message_content,
    send_stored_content,
    store_message_media,
)
from app.services.filters import GroupFilterService
from app.services.facebook_promo_ai import FacebookPromoAIService
from app.services.posting import PostingService
from app.services.reports import ReportService
from app.services.roles import RoleManagementService
from app.services.schedule import ScheduleService
from app.services.target_preferences import TargetPreferencesService
from app.services.ui_preferences import UiPreferencesService
from app.services.warnings import WarningService
from app.repositories.audit import AuditRepository

router = Router(name="navigation")


def _section_text(section: str) -> str:
    if section == "Home":
        return (
            "🏠 Home\n\n"
            "Start with the task you want to do next."
        )
    if section == "Create":
        return (
            "⚡ Create\n\n"
            "Pick what you want to send or create."
        )
    if section == "Review":
        return (
            "✅ Review\n\n"
            "Check pending items, schedules, or alerts."
        )
    if section == "Status":
        return (
            "📊 Status\n\n"
            "See channels, groups, bots, and reports."
        )
    if section == "More":
        return (
            "⚙️ More\n\n"
            "Power tools still live here.\n"
            "Nothing is removed, only organized deeper."
        )
    actions = ", ".join(SECTION_ACTIONS.get(section, []))
    return (
        f"{section} Center\n\n"
        f"Available actions: {actions}\n"
        "Pick one to continue."
    )


def _facebook_promo_summary_text(profile) -> str:
    access_ready = "Connected" if profile.page_id and profile.page_access_token else "Needs setup"
    ai_ready = "Ready" if profile.brand_notes or profile.strategy_notes else "Needs brief"
    status_label = "ACTIVE" if profile.status == "ACTIVE" else "INACTIVE"
    preferences = FacebookPromoAIService.describe_preferences(profile)
    lines = [
        "🧠 Facebook Promo AI",
        "",
        "This automation does not post right away.",
        "It first learns what the user really wants, asks better follow-up questions, then prepares a stronger promo draft.",
        "",
        f"Status: {status_label}",
        f"Facebook access: {access_ready}",
        f"AI brief: {ai_ready}",
        f"Tone memory: {preferences['tone']}",
        f"CTA memory: {preferences['cta']}",
    ]
    if profile.page_id:
        lines.append(f"Page ID: {profile.page_id}")
    if profile.last_goal:
        lines.extend(["", f"Last goal: {profile.last_goal[:160]}"])
    lines.extend([
        "",
        "Best next steps:",
        "1. Connect Page ID and access token",
        "2. Tell AI about your brand, audience, and promo style",
        "3. Activate only after the brief is ready",
    ])
    return "\n".join(lines)


def _facebook_promo_missing_setup_text(profile) -> str:
    missing: list[str] = []
    if not profile.page_id or not profile.page_access_token:
        missing.append("- Facebook access")
    if not profile.brand_notes and not profile.strategy_notes:
        missing.append("- AI brief")
    return "\n".join(
        [
            "Facebook Promo AI setup needed",
            "",
            "Before a new promo task, the bot needs this setup:",
            *missing,
            "",
            "Facebook access is already saved." if profile.page_id and profile.page_access_token else "Start by saving Facebook access.",
            "Next: tell AI about your business, audience, offer style, and how it should write.",
        ]
    )


def _facebook_promo_access_text(profile, mask_token_fn) -> str:
    readiness = FacebookPromoAIService.build_access_readiness(profile)
    issues = "\n".join(f"- {item}" for item in readiness.issues) if readiness.issues else "- none"
    return "\n".join(
        [
            "🔑 Facebook access",
            "",
            "Save the Page ID and Page access token here first.",
            "Later this agent will use them for preview, publish, and scheduling.",
            "Need help? Tap Access Setup Help.",
            "",
            f"Page ID: {profile.page_id or 'Not saved yet'}",
            f"Access token: {mask_token_fn(profile.page_access_token)}",
            f"Setup status: {'Ready for dry-run validation' if readiness.ready else 'Needs setup'}",
            "",
            "Access issues:",
            issues,
            "",
            f"Next step: {readiness.next_step}",
            "",
            "Use the buttons below to update or clear access.",
        ]
    )


def _facebook_promo_access_help_text() -> str:
    return "\n".join(
        [
            "Facebook access setup help",
            "",
            "What you need:",
            "- Page ID: the Facebook Page where posts will go.",
            "- Page access token: a token for that Page, not a normal user password.",
            "",
            "Recommended order:",
            "1. Save Page ID.",
            "2. Save Page access token.",
            "3. Run Dry Run Validate.",
            "4. Run live Validate only after the owner enables Facebook Graph live mode.",
            "",
            "Token permissions usually needed:",
            "- permission to read the Page identity",
            "- permission to create Page posts",
            "",
            "Safety notes:",
            "- The bot masks the saved token.",
            "- The bot tries to delete your token message after saving.",
            "- Do not paste tokens in group chats.",
            "- Rotate exposed tokens after testing.",
            "- Saving access does not publish anything by itself.",
        ]
    )


def _facebook_promo_brief_text(profile) -> str:
    notes = profile.strategy_notes or profile.brand_notes or "Nothing saved yet."
    preferences = FacebookPromoAIService.describe_preferences(profile)
    return "\n".join(
        [
            "💬 AI brief",
            "",
            "Tell the agent about your business in your own language.",
            "It will use this to ask smarter questions and recommend better promo angles.",
            "",
            f"Saved brief:\n{notes[:700]}",
            "",
            "Current style memory:",
            f"- Tone: {preferences['tone']}",
            f"- Emoji: {preferences['emoji']}",
            f"- CTA: {preferences['cta']}",
            f"- Image style: {preferences['image']}",
            "",
            "Good things to mention:",
            "- what you sell",
            "- who you sell to",
            "- what kind of post works best",
            "- what tone or image style you prefer",
        ]
    )


def _facebook_promo_preferences_text(profile) -> str:
    preferences = FacebookPromoAIService.describe_preferences(profile)
    return "\n".join(
        [
            "ðŸŽ› Style memory",
            "",
            "These default preferences help the first draft start closer to your brand style.",
            "You can still refine any draft later.",
            "",
            f"Tone: {preferences['tone']}",
            f"Emoji style: {preferences['emoji']}",
            f"CTA style: {preferences['cta']}",
            f"Image style: {preferences['image']}",
            "",
            "Tap an option below to update what the agent should remember.",
        ]
    )


def _facebook_promo_hub_keyboard(profile) -> object:
    return build_facebook_promo_simple_keyboard(
        bool(profile.page_id and profile.page_access_token),
    )


def _facebook_promo_working_plan_text(profile) -> str:
    brand = profile.brand_notes or "Not set yet"
    strategy = profile.strategy_notes or "Not set yet"
    status_line = "Ready to activate" if FacebookPromoAIService.is_ready(profile) else "Needs setup first"
    return "\n".join(
        [
            "📋 Working plan",
            "",
            f"Current state: {status_line}",
            "",
            f"Brand / niche:\n{brand[:320]}",
            "",
            f"AI strategy memory:\n{strategy[:500]}",
            "",
            "How this will work:",
            "1. User asks for a promo task",
            "2. Agent asks better follow-up questions",
            "3. Agent recommends the best post direction",
            "4. Agent prepares better text and image ideas",
            "5. Agent waits for approval before real posting",
        ]
    )


def _facebook_promo_sample_text() -> str:
    return "\n".join(
        [
            "🧪 Sample conversation",
            "",
            "User: post koro",
            "Agent: Sure. Best post বানানোর আগে goal ta clear করি 👇",
            "- 📣 Promotion",
            "- 💬 Engagement",
            "- 🛍 Product sale",
            "- 🎉 Offer campaign",
            "",
            "User: product sale",
            "Agent: Great. Kon product, kon audience, ar image lagbe ki?",
            "",
            "This means the agent will think first, then create.",
        ]
    )


def _facebook_promo_guide_text() -> str:
    return "\n".join(
        [
            "Facebook Promo AI guide",
            "",
            "Simple flow:",
            "1. Save Facebook Page ID and Page access token.",
            "2. Add brand/AI brief so the bot understands your business.",
            "3. Start New Promo Task and answer the bot's questions.",
            "4. Generate draft, refine if needed, then preview image generation.",
            "5. Save campaign draft, approve it for publish, then run Dry Run Publish.",
            "6. Publish Now only opens a final confirmation screen.",
            "",
            "Safety rules:",
            "- The bot never posts immediately from the first request.",
            "- Live Facebook posting stays blocked unless Graph API is enabled.",
            "- Image generation stays blocked while Alibaba dry-run is ON.",
            "- Free users are limited by monthly image quota and premium model blocks.",
            "- Photo posts require a public HTTPS image URL.",
            "",
            "Best practice:",
            "- Use Dry Run Validate after saving access.",
            "- Use Dry Run Publish before final confirmation.",
            "- Keep tokens private and rotate exposed API keys after setup.",
        ]
    )


FACEBOOK_PROMO_GOAL_LABELS: dict[str, str] = {
    "PROMO": "Promotion",
    "ENGAGEMENT": "Engagement",
    "SALE": "Product Sale",
    "OFFER": "Offer Campaign",
    "BRAND": "Brand Awareness",
}


def _facebook_promo_request_prompt() -> str:
    return (
        "🚀 New promo task\n\n"
        "Tell me what you want in your own language.\n"
        "Example: ladies bag er jonno premium promo chai, image shoho.\n\n"
        "I will not start posting right away. I will first understand the goal, ask better follow-up questions, and then prepare a stronger plan."
    )


def _facebook_promo_goal_prompt(pending) -> str:
    return "\n".join(
        [
            "🎯 Pick the main goal first",
            "",
            f"Your request: {pending.user_request or '-'}",
            "",
            "This helps the agent choose the best promo direction before it writes anything.",
        ]
    )


def _facebook_promo_topic_prompt(pending) -> str:
    return "\n".join(
        [
            f"Good. Goal: {pending.goal_label or pending.goal_key}",
            "",
            "Now tell me what the post is about.",
            "Example: ladies bag, summer collection, restaurant combo offer, digital course, skincare product.",
        ]
    )


def _facebook_promo_audience_prompt(pending) -> str:
    return "\n".join(
        [
            f"Topic: {pending.topic or '-'}",
            "",
            "Who is the main audience?",
            "Example: women 20-35, local restaurant customers, premium buyers, parents, students.",
        ]
    )


def _facebook_promo_image_prompt(pending) -> str:
    return "\n".join(
        [
            f"Audience: {pending.audience or '-'}",
            "",
            "Do you want image support for this kind of promo?",
            "You can decide directly, or let the agent recommend it later.",
        ]
    )


def _facebook_promo_task_summary_text(pending) -> str:
    return "\n".join(
        [
            "✅ Promo task clarified",
            "",
            f"Goal: {pending.goal_label or pending.goal_key or '-'}",
            f"Original request: {pending.user_request or '-'}",
            f"Topic: {pending.topic or '-'}",
            f"Audience: {pending.audience or '-'}",
            f"Image mode: {pending.image_mode or '-'}",
            f"Selected angle: {pending.selected_angle or '-'}",
            "",
            "Saved to AI working memory.",
            "Next phase will use this to ask deeper strategy questions and then generate stronger drafts.",
        ]
    )


def _facebook_promo_recommendation_text(pending, recommendations) -> str:
    lines = [
        "🧠 Recommended promo directions",
        "",
        f"Goal: {pending.goal_label or pending.goal_key or '-'}",
        f"Topic: {pending.topic or '-'}",
        f"Audience: {pending.audience or '-'}",
        "",
        "Based on your input, these are the best directions to continue with:",
        "",
    ]
    for index, recommendation in enumerate(recommendations[:3], start=1):
        lines.append(f"{index}. {recommendation.title}")
        lines.append(f"   {recommendation.summary}")
        lines.append("")
    lines.append("Pick the direction you want the agent to build on.")
    return "\n".join(lines)


def _facebook_promo_strategy_plan_text(pending, plan) -> str:
    return "\n".join(
        [
            "📋 Strategy plan",
            "",
            f"Goal: {pending.goal_label or pending.goal_key or '-'}",
            f"Topic: {pending.topic or '-'}",
            f"Audience: {pending.audience or '-'}",
            f"Chosen angle: {plan.angle_title}",
            "",
            f"Positioning:\n{plan.positioning}",
            "",
            f"Hook style:\n{plan.hook_style}",
            "",
            f"Copy direction:\n{plan.copy_direction}",
            "",
            f"CTA direction:\n{plan.cta_direction}",
            "",
            f"Image direction:\n{plan.image_direction}",
            "",
            "If you want, refine this plan first. Otherwise save it and move to draft generation next.",
        ]
    )


def _facebook_promo_draft_text(draft) -> str:
    return "\n".join(
        [
            "✍️ Draft preview",
            "",
            f"Headline:\n{draft.headline}",
            "",
            f"Main copy:\n{draft.primary_copy}",
            "",
            f"Short version:\n{draft.short_copy}",
            "",
            f"CTA:\n{draft.cta}",
            "",
            f"Hashtags:\n{draft.hashtags}",
            "",
            f"Image concept:\n{draft.image_concept}",
            "",
            "This is the first structured draft from the saved strategy plan. Next phases will make this AI-generated, refinable, and publish-ready.",
        ]
    )


def _facebook_promo_draft_v2_text(draft, generated_image=None) -> str:
    text = _facebook_promo_draft_text(draft)
    if not generated_image:
        return text
    image_lines = [
        "",
        "Generated image:",
        f"Model: {generated_image.model}",
        f"Created: {generated_image.created_at}",
        f"URL: {generated_image.image_urls[0] if generated_image.image_urls else 'Not available'}",
    ]
    return text + "\n" + "\n".join(image_lines)


def _facebook_promo_variant_compare_text(variants: dict[str, object]) -> str:
    lines = [
        "🧩 Draft variants",
        "",
        "Here are quick compare versions from the same draft:",
        "",
    ]
    ordered_labels = ["Base", "Premium", "Short", "Urgent"]
    for label in ordered_labels:
        draft = variants.get(label)
        if not draft:
            continue
        lines.extend(
            [
                f"{label}:",
                f"Headline: {draft.headline}",
                f"Short copy: {draft.short_copy}",
                f"CTA: {draft.cta}",
                "",
            ]
        )
    lines.append("If one direction feels close, use the preset buttons or refine the draft in your own words.")
    return "\n".join(lines)


def _facebook_promo_image_preview_text(policy, image_prompt: str | None) -> str:
    lines = [
        "Image generation preview",
        "",
        policy.message,
        "",
        f"User tier: {policy.user_tier}",
        f"Selected model: {policy.model or 'Blocked'}",
        f"Fallback order: {', '.join(policy.fallback_models) if policy.fallback_models else 'None'}",
        f"Monthly usage: {policy.monthly_used}/{policy.monthly_limit}",
        f"Global usage: {policy.global_used}/{policy.global_limit}",
        f"Dry run: {'ON' if policy.dry_run else 'OFF'}",
        "",
    ]
    if not image_prompt:
        lines.append("Generate a draft first, then image prompt preview will appear here.")
        return "\n".join(lines)
    lines.extend(
        [
            "Prompt preview:",
            image_prompt[:1000],
            "",
            "No image API call was made from this preview.",
        ]
    )
    if policy.allowed and policy.dry_run:
        lines.append("Confirm is available for flow testing, but dry-run mode will block real quota use.")
    return "\n".join(lines)


def _facebook_promo_image_confirm_text(policy) -> str:
    lines = [
        "Image generation confirmation",
        "",
        policy.message,
        "",
        f"User tier: {policy.user_tier}",
        f"Selected model: {policy.model or 'Blocked'}",
        f"Monthly usage: {policy.monthly_used}/{policy.monthly_limit}",
        f"Global usage: {policy.global_used}/{policy.global_limit}",
        f"Dry run: {'ON' if policy.dry_run else 'OFF'}",
        "",
    ]
    if policy.dry_run:
        lines.append("Blocked safely: dry-run mode is ON, so no Alibaba quota was used.")
    elif not policy.allowed:
        lines.append("Blocked safely: this request is not allowed right now.")
    else:
        lines.append("Real image generation adapter will run in the next implementation phase.")
    return "\n".join(lines)


def _facebook_promo_image_result_text(result) -> str:
    lines = [
        "Image generation result",
        "",
        result.message,
        "",
    ]
    if result.request:
        lines.extend(
            [
                f"Model: {result.request.model}",
                f"Endpoint: {result.request.url}",
                "Quota mode: count only after successful image URL",
                "",
            ]
        )
    if result.image_urls:
        lines.append("Generated image URLs:")
        lines.extend(result.image_urls[:3])
        lines.append("")
        lines.append("Saved to the current promo draft.")
    else:
        lines.append("No image was generated.")
    return "\n".join(lines)


def _facebook_promo_image_safety_status_text(policy, service: FacebookPromoAIService) -> str:
    model_rankings = FacebookPromoAIService.image_model_rankings()
    paid_models = ", ".join(FacebookPromoAIService.image_model_order_for_tier("PAID"))
    free_models = ", ".join(FacebookPromoAIService.image_model_order_for_tier("FREE"))
    top_ranked = "\n".join(f"{rank}. {model} - {note}" for rank, model, note in model_rankings[:6])
    return "\n".join(
        [
            "Image generation safety status",
            "",
            policy.message,
            "",
            f"Your tier: {policy.user_tier}",
            f"Selected default model: {policy.model or 'Blocked'}",
            f"Monthly usage: {policy.monthly_used}/{policy.monthly_limit}",
            f"Global usage: {policy.global_used}/{policy.global_limit}",
            f"API enabled: {'YES' if service.alibaba_image_api_enabled else 'NO'}",
            f"Dry-run: {'ON' if service.alibaba_image_dry_run else 'OFF'}",
            f"Admin-only live rollout: {'ON' if service.alibaba_image_admin_live_only else 'OFF'}",
            "",
            "Free user model order:",
            free_models,
            "",
            "Paid/Admin model order:",
            paid_models,
            "",
            "Top image ranking:",
            top_ranked,
            "",
            "Safety rule: usage count increases only after a successful image URL is returned.",
        ]
    )


def _facebook_promo_generated_image_caption(result) -> str:
    model = result.request.model if result.request else "unknown"
    return "\n".join(
        [
            "Generated promo image",
            f"Model: {model}",
            "Saved to the current promo draft.",
        ]
    )


async def _safe_send_generated_image(callback: CallbackQuery, result) -> bool:
    if not result.ok or not result.image_urls:
        return False
    try:
        await callback.message.answer_photo(
            photo=result.image_urls[0],
            caption=_facebook_promo_generated_image_caption(result),
            reply_markup=build_facebook_promo_draft_v4_keyboard(),
        )
        return True
    except TelegramBadRequest:
        return False


def _facebook_promo_campaigns_text(campaigns) -> str:
    lines = [
        "📚 Saved campaign drafts",
        "",
    ]
    if not campaigns:
        lines.append("No campaign drafts saved yet.")
        lines.append("")
        lines.append("Generate a good draft first, then save it here.")
        return "\n".join(lines)
    for index, campaign in enumerate(campaigns[:10], start=1):
        lines.extend(
            [
                f"{index}. {campaign.title}",
                f"   Status: {campaign.status}",
                f"   Goal: {campaign.goal}",
                f"   Topic: {campaign.topic}",
                f"   Saved: {campaign.created_at}",
                "",
            ]
        )
    lines.append("These saved drafts will become the base for future publish, approve, and schedule steps.")
    return "\n".join(lines)


def _facebook_promo_status_label(status: str) -> str:
    return {
        "DRAFT": "Draft",
        "READY_TO_PUBLISH": "Ready to publish",
        "PUBLISHED": "Published",
    }.get(status, status.replace("_", " ").title())


def _facebook_promo_campaign_button_items(campaigns) -> list[tuple[int, str]]:
    prefix_map = {
        "DRAFT": "Draft",
        "READY_TO_PUBLISH": "Ready",
        "PUBLISHED": "Published",
    }
    return [
        (index, f"{prefix_map.get(item.status, item.status.title())}: {item.title}")
        for index, item in enumerate(campaigns)
    ]


def _facebook_promo_campaigns_v2_text(campaigns) -> str:
    lines = [
        "Saved campaign drafts",
        "",
    ]
    if not campaigns:
        lines.append("No campaign drafts saved yet.")
        lines.append("")
        lines.append("Generate a good draft first, then save it here.")
        return "\n".join(lines)

    draft_count = sum(1 for item in campaigns if item.status == "DRAFT")
    ready_count = sum(1 for item in campaigns if item.status == "READY_TO_PUBLISH")
    published_count = sum(1 for item in campaigns if item.status == "PUBLISHED")
    lines.extend(
        [
            f"Draft: {draft_count} | Ready: {ready_count} | Published: {published_count}",
            "",
        ]
    )
    for index, campaign in enumerate(campaigns[:10], start=1):
        lines.extend(
            [
                f"{index}. {campaign.title}",
                f"   Status: {_facebook_promo_status_label(campaign.status)}",
                f"   Goal: {campaign.goal}",
                f"   Topic: {campaign.topic}",
                f"   Saved: {campaign.created_at}",
                "",
            ]
        )
    lines.append("Open a campaign to edit, approve, publish, or reuse it.")
    return "\n".join(lines)


def _facebook_promo_campaign_detail_text(campaign, draft) -> str:
    return "\n".join(
        [
            "📄 Saved campaign draft",
            "",
            f"Title: {campaign.title}",
            f"Status: {campaign.status}",
            f"Goal: {campaign.goal}",
            f"Topic: {campaign.topic}",
            f"Saved: {campaign.created_at}",
            "",
            f"Headline:\n{draft.headline}",
            "",
            f"Main copy:\n{draft.primary_copy}",
            "",
            f"Short version:\n{draft.short_copy}",
            "",
            f"CTA:\n{draft.cta}",
            "",
            f"Hashtags:\n{draft.hashtags}",
            "",
            f"Image concept:\n{draft.image_concept}",
        ]
    )


def _facebook_promo_campaign_detail_v2_text(campaign, draft, publish_checklist=None) -> str:
    text = _facebook_promo_campaign_detail_text(campaign, draft)
    extra: list[str] = []
    if getattr(campaign, "published_at", None):
        extra.append(f"Published: {campaign.published_at}")
    if getattr(campaign, "facebook_post_id", None):
        extra.append(f"Facebook post id: {campaign.facebook_post_id}")
    generated_image = FacebookPromoAIService.parse_generated_image(getattr(campaign, "image_json", None))
    if generated_image:
        extra.append(f"Image model: {generated_image.model}")
        extra.append(f"Image created: {generated_image.created_at}")
        if generated_image.image_urls:
            extra.append(f"Image URL: {generated_image.image_urls[0]}")
    if publish_checklist:
        extra.extend(
            [
                "",
                "Publish checklist:",
                f"Type: {publish_checklist.publish_type}",
                f"Live ready: {'YES' if publish_checklist.live_ready else 'NO'}",
            ]
        )
        extra.extend(f"- {item}" for item in publish_checklist.checks)
        if publish_checklist.blockers:
            extra.append("Blockers:")
            extra.extend(f"- {item}" for item in publish_checklist.blockers)
    if not extra:
        return text
    return text.replace(
        f"Saved: {campaign.created_at}",
        f"Saved: {campaign.created_at}\n" + "\n".join(extra),
        1,
    )


def _facebook_promo_campaign_keyboard_for(campaign, index: int):
    if campaign.status == "PUBLISHED":
        return build_facebook_promo_published_campaign_detail_keyboard(index)
    if campaign.status == "READY_TO_PUBLISH":
        return build_facebook_promo_ready_campaign_detail_keyboard(index)
    return build_facebook_promo_campaign_detail_keyboard(index)


def _facebook_promo_ready_queue_text(campaigns) -> str:
    lines = [
        "🚀 Ready to publish queue",
        "",
    ]
    if not campaigns:
        lines.append("No campaign is marked ready to publish yet.")
        lines.append("")
        lines.append("Approve a saved campaign first to see it here.")
        return "\n".join(lines)
    for index, campaign in enumerate(campaigns[:10], start=1):
        lines.extend(
            [
                f"{index}. {campaign.title}",
                f"   Goal: {campaign.goal}",
                f"   Topic: {campaign.topic}",
                f"   Saved: {campaign.created_at}",
                "",
            ]
        )
    lines.append("These drafts are approved and waiting for the real Facebook publish connector.")
    return "\n".join(lines)


def _facebook_promo_published_history_text(campaigns) -> str:
    lines = [
        "Published campaign history",
        "",
    ]
    if not campaigns:
        lines.append("No campaign has been published from Facebook Promo AI yet.")
        lines.append("")
        lines.append("After a real publish succeeds, it will appear here with the Facebook post id.")
        return "\n".join(lines)
    for index, campaign in enumerate(campaigns[:10], start=1):
        lines.extend(
            [
                f"{index}. {campaign.title}",
                f"   Goal: {campaign.goal}",
                f"   Topic: {campaign.topic}",
                f"   Published: {campaign.published_at or 'Unknown'}",
                f"   Facebook post id: {campaign.facebook_post_id or 'Not returned'}",
                f"   Saved: {campaign.created_at}",
                "",
            ]
        )
    lines.append("Open any item to reuse the draft or review the final published copy.")
    return "\n".join(lines)


def _facebook_promo_publish_dry_run_text(result) -> str:
    lines = [
        "Facebook publish dry run",
        "",
        result.message,
    ]
    if not result.ok or not result.request:
        return "\n".join(lines)

    payload = result.request.payload
    message = payload.get("message") or payload.get("caption", "")
    preview = message[:700] + ("..." if len(message) > 700 else "")
    image_url = payload.get("url")
    lines.extend(
        [
            "",
            f"Method: {result.request.method}",
            f"URL: {result.request.url}",
            "Auth: Bearer <PAGE_ACCESS_TOKEN>",
            f"Payload type: {'photo post' if image_url else 'text post'}",
            *(["Image URL: " + image_url] if image_url else []),
            "",
            "Payload preview:",
            preview,
            "",
            "No request was sent to Facebook in this dry run.",
        ]
    )
    return "\n".join(lines)


def _facebook_promo_access_dry_run_text(result) -> str:
    lines = [
        "Facebook access validation dry run",
        "",
        result.message,
    ]
    if not result.ok or not result.request:
        return "\n".join(lines)

    lines.extend(
        [
            "",
            f"Method: {result.request.method}",
            f"URL: {result.request.url}",
            "Auth: Bearer <PAGE_ACCESS_TOKEN>",
            f"Query: {result.request.payload}",
            "",
            "No request was sent to Facebook in this dry run.",
        ]
    )
    return "\n".join(lines)


def _facebook_promo_graph_response_text(title: str, result) -> str:
    lines = [
        title,
        "",
        result.message,
    ]
    if result.status_code is None and "disabled" in result.message.lower():
        lines.extend(
            [
                "",
                "No live request was sent.",
                "Use Dry Run first, then ask the owner to enable Facebook Graph live posting when ready.",
            ]
        )
    if result.status_code is not None:
        lines.append(f"Status code: {result.status_code}")
    if result.body:
        body = result.body[:900] + ("..." if len(result.body) > 900 else "")
        lines.extend(["", "Response body:", body])
    return "\n".join(lines)


def _facebook_promo_publish_confirm_text(result) -> str:
    lines = [
        "Final Facebook publish confirmation",
        "",
        "This is the last safety step before a live Facebook post.",
        "",
        result.message,
    ]
    if not result.ok or not result.request:
        lines.extend(["", "Live publish is blocked until the issue above is fixed."])
        return "\n".join(lines)

    message = result.request.payload.get("message") or result.request.payload.get("caption", "")
    preview = message[:900] + ("..." if len(message) > 900 else "")
    image_url = result.request.payload.get("url")
    lines.extend(
        [
            "",
            f"Method: {result.request.method}",
            f"URL: {result.request.url}",
            "Auth: Bearer <PAGE_ACCESS_TOKEN>",
            f"Payload type: {'photo post' if image_url else 'text post'}",
            *(["Image URL: " + image_url] if image_url else []),
            "",
            "Post preview:",
            preview,
            "",
            "If this looks correct, press Confirm Live Publish.",
        ]
    )
    return "\n".join(lines)


def _entity_input_prompt(section: str) -> str:
    singular = "channel" if section == "Channels" else "group"
    return (
        f"Add {singular}\n\n"
        f"Send the {singular} username or numeric chat id.\n"
        "Optional title can be added with this format:\n"
        "@identifier | Friendly Title\n\n"
        "Need to leave this flow? Send /cancel"
    )


def _menu_keys_for_mode(mode: str) -> tuple[str, ...]:
    if mode == "PRO":
        return (
            "Home",
            "Create",
            "Review",
            "Status",
            "Channels",
            "Groups",
            "Bots",
            "Reports",
            "Automation",
            "Settings",
            "More",
        )
    return ("Home", "Create", "Review", "Status", "More")


def _menu_keyboard_for_profile(profile, ui_mode: str = "SIMPLE") -> object:
    visible_keys = get_visible_main_menu_keys(profile, _menu_keys_for_mode(ui_mode))
    return build_main_menu_keyboard(visible_keys)


def _resolve_schedule_spec_for_pending(
    pending_schedule,
    raw_value: str,
    parse_schedule_time_fn,
):
    mode = pending_schedule.schedule_mode
    normalized = raw_value.strip()

    if mode == "DAILY":
        parsed = parse_schedule_time_fn(normalized)
        if ":" not in normalized or parsed.recurrence_key is not None:
            raise ValueError("Use HH:MM for daily schedules.")
        parsed.recurrence_key = "DAILY"
        return parsed

    if mode == "WEEKLY":
        parsed = parse_schedule_time_fn(normalized)
        parsed.recurrence_key = "WEEKLY"
        return parsed

    if mode == "MONTHLY":
        parsed = parse_schedule_time_fn(normalized)
        parsed.recurrence_key = "MONTHLY"
        return parsed

    if mode == "WORKDAYS":
        parsed = parse_schedule_time_fn(normalized)
        parsed.recurrence_key = "WORKDAYS"
        return parsed

    if mode == "WEEKEND":
        parsed = parse_schedule_time_fn(normalized)
        parsed.recurrence_key = "WEEKEND"
        return parsed

    if mode == "DELAY":
        parsed = parse_schedule_time_fn(normalized)
        if "-" not in normalized:
            raise ValueError("Use d-h-m-s for delay schedules.")
        parsed.recurrence_key = None
        return parsed

    if mode == "EXACT":
        parsed = parse_schedule_time_fn(normalized)
        if parsed.recurrence_key is not None:
            raise ValueError("Use exact date and time for this schedule type.")
        return parsed

    return parse_schedule_time_fn(normalized)


def _post_prompt(channel_identifier: str, channel_title: str | None) -> str:
    label = channel_title or channel_identifier
    return (
        f"📝 Post to {label}\n\n"
        "Send one thing now:\n"
        "- text\n"
        "- photo\n"
        "- video\n"
        "- document\n\n"
        "Caption is supported for media too.\n\n"
        "Need to leave this flow? Send /cancel"
    )


def _broadcast_prompt(target_count: int) -> str:
    return (
        f"📤 Broadcast to {target_count} active channels\n\n"
        "Send one thing to publish everywhere:\n"
        "- text\n"
        "- photo\n"
        "- video\n"
        "- document\n\n"
        "Caption is supported for media too.\n\n"
        "Need to leave this flow? Send /cancel"
    )


def _broadcast_select_text(total_count: int, selected_count: int) -> str:
    return (
        "🎯 Select broadcast targets\n\n"
        f"Available active channels: {total_count}\n"
        f"Selected: {selected_count}\n\n"
        "⭐ Favorites appear first. 🕘 Recent targets come next.\n"
        "Tap channels to toggle selection, or use ☆ to save favorites."
    )


def _channel_picker_text(kind: str, ranked_channels: list[tuple[object, bool, bool]]) -> str:
    favorite_count = len([1 for _, is_favorite, _ in ranked_channels if is_favorite])
    recent_count = len([1 for _, _, is_recent in ranked_channels if is_recent])
    if kind == "post":
        title = "📝 Choose a channel for posting"
    elif kind == "schedule":
        title = "⏰ Choose a channel for scheduling"
    else:
        title = "📢 Choose a channel"
    return (
        f"{title}\n\n"
        f"⭐ Favorites: {favorite_count}\n"
        f"🕘 Recent: {recent_count}\n\n"
        "Favorites show first, then recent targets.\n"
        "Tap a channel to continue. Tap ☆ to save a favorite."
    )


def _search_empty_text(context: str, query: str) -> str:
    title_map = {
        "post": "📝 Post search",
        "schedule": "⏰ Schedule search",
        "broadcast": "📤 Broadcast search",
    }
    return (
        f"{title_map.get(context, '🔎 Search')}\n\n"
        f'No match found for: "{query.strip()}"\n\n'
        "Try a shorter title, username, or just one keyword.\n"
        "Or use the quick buttons below."
    )


def _search_results_text(
    context: str,
    query: str,
    filtered_items: list[tuple[int, str, str | None, bool, bool]],
) -> str:
    title_map = {
        "post": "📝 Search results",
        "schedule": "⏰ Search results",
        "broadcast": "📤 Search results",
    }
    shown = min(len(filtered_items), 10)
    return (
        f"{title_map.get(context, '🔎 Search results')}\n\n"
        f'Query: "{query.strip()}"\n'
        f"Matches: {len(filtered_items)}\n"
        f"Showing: 1-{shown}\n\n"
        "Tap a result to continue."
    )


def _filter_ranked_channel_items(
    ranked_items: list[tuple[int, str, str | None, bool, bool]],
    filter_mode: str,
) -> list[tuple[int, str, str | None, bool, bool]]:
    if filter_mode == "favorites":
        return [item for item in ranked_items if item[3]]
    return ranked_items


def _search_ranked_channel_items(
    ranked_items: list[tuple[int, str, str | None, bool, bool]],
    query: str,
) -> list[tuple[int, str, str | None, bool, bool]]:
    needle = query.strip().lower()
    if not needle:
        return ranked_items
    return [
        item
        for item in ranked_items
        if needle in (item[2] or "").lower() or needle in item[1].lower()
    ]


def _picker_search_prompt(context: str) -> str:
    label = {
        "post": "posting",
        "schedule": "scheduling",
        "broadcast": "broadcast",
    }.get(context, "target search")
    return (
        f"🔎 Search for {label}\n\n"
        "Send part of the channel name or identifier.\n"
        "Example: news, deals, @my_channel\n\n"
        "Need to leave this flow? Send /cancel"
    )


def _schedule_time_prompt(channel_identifier: str, channel_title: str | None) -> str:
    label = channel_title or channel_identifier
    return (
        f"Schedule for {label}\n\n"
        "All times are treated as Bangladesh time (Asia/Dhaka).\n\n"
        "Send schedule time in one of these formats:\n"
        "YYYY-MM-DD HH:MM\n"
        "d / w / m  (repeat daily / weekly / monthly)\n"
        "d-h-m-s\n"
        "HH:MM\n"
        "10m / 2h / 1d\n"
        "tomorrow 09:30\n\n"
        "Examples:\n"
        "2026-04-19 21:30\n"
        "d\n"
        "0-00-00-30\n"
        "21:30\n"
        "30m"
    )


def _schedule_mode_text(channel_identifier: str, channel_title: str | None) -> str:
    label = channel_title or channel_identifier
    return (
        f"⏰ Schedule for {label}\n\n"
        "Choose the schedule type first.\n"
        "This keeps the next step much simpler."
    )


def _schedule_time_prompt_for_mode(
    channel_identifier: str,
    channel_title: str | None,
    schedule_mode: str | None,
) -> str:
    label = channel_title or channel_identifier
    if schedule_mode == "EXACT":
        hint = (
            "Send the exact time in Bangladesh time.\n"
            "Format: YYYY-MM-DD HH:MM\n\n"
            "Example:\n2026-04-21 22:30"
        )
    elif schedule_mode == "DAILY":
        hint = (
            "Send the daily posting time.\n"
            "Format: HH:MM\n\n"
            "Example:\n21:30\n\n"
            "It will repeat every day at that time."
        )
    elif schedule_mode == "WEEKLY":
        hint = (
            "Now choose the time for the selected weekday.\n"
            "Best format: HH:MM\n\n"
            "Example:\n21:30"
        )
    elif schedule_mode == "MONTHLY":
        hint = (
            "Now choose the time for the selected monthly date.\n"
            "Best format: HH:MM\n\n"
            "Example:\n10:00"
        )
    elif schedule_mode == "DELAY":
        hint = (
            "Send a delay.\n"
            "Format: d-h-m-s\n\n"
            "Example:\n0-00-10-00"
        )
    elif schedule_mode == "WORKDAYS":
        hint = (
            "Choose a time for workdays.\n"
            "This will run Monday to Friday.\n\n"
            "Best format: HH:MM\n\n"
            "Example:\n09:00"
        )
    elif schedule_mode == "WEEKEND":
        hint = (
            "Choose a time for weekends.\n"
            "This will run Saturday and Sunday.\n\n"
            "Best format: HH:MM\n\n"
            "Example:\n10:00"
        )
    else:
        hint = (
            "All times are treated as Bangladesh time (Asia/Dhaka).\n\n"
            "Send schedule time in one of these formats:\n"
            "YYYY-MM-DD HH:MM\n"
            "d / w / m  (repeat daily / weekly / monthly)\n"
            "d-h-m-s"
        )
    return f"⏰ Schedule for {label}\n\n{hint}\n\nOr tap a shortcut below."


def _schedule_shortcut_options(schedule_mode: str | None) -> list[tuple[str, str]]:
    if schedule_mode == "DAILY":
        return [
            ("🌅 Morning", "daily_morning"),
            ("☀️ Noon", "daily_noon"),
            ("🌆 Evening", "daily_evening"),
            ("🌙 Night", "daily_night"),
            ("09:00", "daily_0900"),
            ("12:00", "daily_1200"),
            ("18:00", "daily_1800"),
            ("21:00", "daily_2100"),
        ]
    if schedule_mode == "WORKDAYS":
        return [
            ("🌅 Morning", "workdays_morning"),
            ("☀️ Noon", "workdays_noon"),
            ("🌆 Evening", "workdays_evening"),
            ("🌙 Night", "workdays_night"),
            ("09:00", "workdays_0900"),
            ("18:00", "workdays_1800"),
        ]
    if schedule_mode == "WEEKEND":
        return [
            ("🌅 Morning", "weekend_morning"),
            ("☀️ Noon", "weekend_noon"),
            ("🌆 Evening", "weekend_evening"),
            ("🌙 Night", "weekend_night"),
            ("10:00", "weekend_1000"),
            ("21:00", "weekend_2100"),
        ]
    if schedule_mode == "DELAY":
        return [
            ("10 min", "delay_10m"),
            ("30 min", "delay_30m"),
            ("1 hour", "delay_1h"),
            ("1 day", "delay_1d"),
        ]
    if schedule_mode == "WEEKLY":
        return [
            ("09:00", "weekly_0900"),
            ("21:00", "weekly_2100"),
        ]
    if schedule_mode == "MONTHLY":
        return [
            ("09:00", "monthly_0900"),
            ("21:00", "monthly_2100"),
        ]
    return [
        ("Tonight 21:00", "exact_2100"),
        ("Tomorrow 09:00", "exact_tomorrow_0900"),
        ("Tomorrow 21:00", "exact_tomorrow_2100"),
        ("+1 hour", "exact_plus_1h"),
    ]


def _resolve_schedule_shortcut_value(pending_schedule, token: str) -> str | None:
    schedule_mode = pending_schedule.schedule_mode
    now = datetime.now(ScheduleService.DASHBOARD_TIMEZONE)
    bucket_map = {
        "morning": "09:00",
        "noon": "12:00",
        "evening": "18:00",
        "night": "21:00",
    }
    if token.startswith("daily_"):
        value = token.split("_", maxsplit=1)[1]
        return bucket_map.get(value, value)
    if token.startswith("workdays_"):
        value = token.split("_", maxsplit=1)[1]
        return bucket_map.get(value, value)
    if token.startswith("weekend_"):
        value = token.split("_", maxsplit=1)[1]
        return bucket_map.get(value, value)
    if token == "delay_10m":
        return "10m"
    if token == "delay_30m":
        return "30m"
    if token == "delay_1h":
        return "1h"
    if token == "delay_1d":
        return "1d"
    if token == "exact_plus_1h":
        return (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    if token == "exact_2100":
        target = now.replace(hour=21, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "exact_tomorrow_0900":
        target = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "exact_tomorrow_2100":
        target = (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "weekly_0900":
        weekday = pending_schedule.selected_weekday if pending_schedule.selected_weekday is not None else now.weekday()
        days_ahead = (weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "weekly_2100":
        weekday = pending_schedule.selected_weekday if pending_schedule.selected_weekday is not None else now.weekday()
        days_ahead = (weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target = (now + timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "monthly_0900":
        year = now.year + (1 if now.month == 12 else 0)
        month = 1 if now.month == 12 else now.month + 1
        desired_day = pending_schedule.selected_monthday or 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(desired_day, last_day)
        target = now.replace(year=year, month=month, day=day, hour=9, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    if token == "monthly_2100":
        year = now.year + (1 if now.month == 12 else 0)
        month = 1 if now.month == 12 else now.month + 1
        desired_day = pending_schedule.selected_monthday or 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(desired_day, last_day)
        target = now.replace(year=year, month=month, day=day, hour=21, minute=0, second=0, microsecond=0)
        return target.strftime("%Y-%m-%d %H:%M")
    return None


def _schedule_message_prompt(channel_identifier: str, channel_title: str | None, scheduled_for: str) -> str:
    label = channel_title or channel_identifier
    return (
        f"Schedule for {label}\n\n"
        f"Time: {scheduled_for}\n\n"
        "Now send text, photo, video, or document to save as a scheduled post.\n"
        "Photo/video/document captions are supported.\n\n"
        "Need to leave this flow? Send /cancel"
    )


def _schedule_confirm_text(pending_schedule) -> str:
    label = pending_schedule.channel_title or pending_schedule.channel_identifier
    repeat_label = pending_schedule.recurrence_key or "ONE-TIME"
    content_type = "media" if pending_schedule.draft_media_path else "text"
    message_preview = pending_schedule.draft_message_text or "-"
    if message_preview == MEDIA_ONLY_SENTINEL:
        message_preview = "[media only]"
    if len(message_preview) > 120:
        message_preview = message_preview[:117] + "..."
    media_name = pending_schedule.draft_media_name or "-"
    return (
        "✅ Confirm schedule\n\n"
        f"Channel: {label}\n"
        f"Time: {pending_schedule.scheduled_for}\n"
        f"Repeat: {repeat_label}\n"
        f"Content type: {content_type}\n"
        f"Media: {media_name}\n"
        f"Preview: {message_preview}\n\n"
        "Confirm to save, edit time, or cancel."
    )


def _schedule_list_text(records) -> str:
    if not records:
        return (
            "⏰ Scheduled posts\n\n"
            "No pending or paused schedules found yet.\n"
            "Next: open `⚡ Create -> ⏰ Schedule` and save your first draft."
        )

    pending_count = len([item for item in records if item.status == "PENDING"])
    paused_count = len([item for item in records if item.status == "PAUSED"])
    recurring_count = len([item for item in records if getattr(item, "recurrence_key", None)])
    lines = [
        "⏰ Scheduled posts",
        "",
        f"Pending: {pending_count}",
        f"Paused: {paused_count}",
        f"Recurring: {recurring_count}",
        "",
        "Current items:",
        "",
    ]
    preview_items = records[:12]
    for item in preview_items:
        label = item.channel_title or item.channel_identifier
        recurrence = f" | repeat={item.recurrence_key}" if getattr(item, "recurrence_key", None) else ""
        lines.append(f"#{item.id} | {label} | {item.scheduled_for} | {item.status}{recurrence}")
    hidden_count = max(len(records) - len(preview_items), 0)
    if hidden_count:
        lines.append(f"... and {hidden_count} more")
    lines.extend(["", "Tip: use /schedule_list anytime to manage them quickly."])
    return "\n".join(lines)


def _bot_input_prompt() -> str:
    return (
        "🤖 Add managed bot\n\n"
        "You can use the simple format first, and only use advanced fields when needed.\n\n"
        "Simple format:\n"
        "@botusername | Display Name | Notes\n\n"
        "Advanced format:\n"
        "@botusername | Display Name | https://health.url | https://action.url | POST | {\"source\":\"{{source}}\",\"bot\":\"{{bot_username}}\"} | Auth-Header | Secret | Notes\n\n"
        "Auth-only format:\n"
        "@botusername | Display Name | https://health.url | https://action.url | Auth-Header | Secret | Notes\n\n"
        "Legacy basic format still works:\n"
        "@botusername | Display Name | https://health.url | https://action.url | Notes\n\n"
        "Supported methods: GET, POST, PUT, PATCH, DELETE\n"
        "Available payload placeholders: {{source}}, {{bot_username}}, {{display_name}}, {{triggered_at}}\n\n"
        "Only the bot username is required."
    )


def _bot_list_text(records) -> str:
    if not records:
        return (
            "🤖 Managed bots\n\n"
            "No managed bots found yet.\n"
            "Next: open `⚙️ More -> 🤖 Bots`, then choose `▶️ Actions` to add one."
        )
    healthy = len([item for item in records if item.status in {"ONLINE", "OK"}])
    lines = [
        "🤖 Managed bots",
        "",
        f"Tracked: {len(records)}",
        f"Healthy: {healthy}",
        "",
        "Current bots:",
        "",
    ]
    preview_items = records[:12]
    for item in preview_items:
        label = item.display_name or item.bot_username
        lines.append(f"- {label} | {item.bot_username} | {item.status}")
    hidden_count = max(len(records) - len(preview_items), 0)
    if hidden_count:
        lines.append(f"... and {hidden_count} more")
        lines.extend(["", "Tip: open Status, Logs, or Settings for more detail."])
    return "\n".join(lines)


def _bot_status_picker_text(records, offset: int = 0, page_size: int = 12) -> str:
    if not records:
        return (
            "🤖 Bot status\n\n"
            "No managed bots found yet.\n"
            "Next: add a bot from `⚙️ More -> 🤖 Bots -> ▶️ Actions`."
        )
    healthy = len([item for item in records if item.status in {"ONLINE", "OK"}])
    issue_count = len(records) - healthy
    return (
        "🤖 Bot status\n\n"
        f"Tracked bots: {len(records)}\n"
        f"Healthy: {healthy}\n"
        f"Needs attention: {issue_count}\n\n"
        f"Showing: {offset + 1}-{min(len(records), offset + page_size)}\n\n"
        "Tap a bot to check its live status."
    )


def _bot_logs_picker_text(records, offset: int = 0, page_size: int = 12) -> str:
    if not records:
        return (
            "🧾 Bot logs\n\n"
            "No managed bots found yet.\n"
            "Next: add a bot first, then logs will start showing here."
        )
    return (
        "🧾 Bot logs\n\n"
        f"Tracked bots: {len(records)}\n"
        f"Showing: {offset + 1}-{min(len(records), offset + page_size)}\n\n"
        "Tap a bot to check recent activity."
    )


def _bot_configs_picker_text(records, offset: int = 0, page_size: int = 12) -> str:
    if not records:
        return (
            "⚙️ Bot configs\n\n"
            "No managed bots found yet.\n"
            "Next: add a bot first to manage its settings here."
        )
    return (
        "⚙️ Bot configs\n\n"
        f"Tracked bots: {len(records)}\n"
        f"Showing: {offset + 1}-{min(len(records), offset + page_size)}\n\n"
        "Tap a bot to review saved settings."
    )


def _bot_detail_text(record) -> str:
    checked = record.last_checked_at.strftime("%Y-%m-%d %H:%M") if record.last_checked_at else "Never"
    return (
        f"🤖 {record.display_name or record.bot_username}\n\n"
        f"Username: {record.bot_username}\n"
        f"Status: {record.status}\n"
        f"Health URL: {record.healthcheck_url or '-'}\n"
        f"Action URL: {record.action_url or '-'}\n"
        f"Action Method: {record.action_method or 'POST'}\n"
        f"Payload Template: {'SET' if record.action_payload_template else '-'}\n"
        f"Auth Header: {record.action_auth_header or '-'}\n"
        f"Action Secret: {'SET' if record.action_secret else '-'}\n"
        f"Last checked: {checked}\n"
        f"Notes: {record.notes or '-'}"
    )


def _bot_config_text(record) -> str:
    return (
        f"⚙️ {record.display_name or record.bot_username}\n\n"
        f"Bot username: {record.bot_username}\n"
        f"Display name: {record.display_name or '-'}\n"
        f"Healthcheck URL: {record.healthcheck_url or '-'}\n"
        f"Action URL: {record.action_url or '-'}\n"
        f"Action method: {record.action_method or 'POST'}\n"
        f"Action payload: {record.action_payload_template or '-'}\n"
        f"Action auth header: {record.action_auth_header or '-'}\n"
        f"Action secret: {'SET' if record.action_secret else '-'}\n"
        f"Notes: {record.notes or '-'}\n"
        f"Registry status: {record.status}"
    )


def _bot_logs_text(record, rows) -> str:
    lines = [f"🧾 {record.display_name or record.bot_username}", "", "Recent activity", ""]
    if not rows:
        lines.append("- No recent activity for this bot yet.")
        return "\n".join(lines)

    for actor_user_id, action_key, _, _, details, created_at in rows:
        timestamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
        suffix = f" | {details}" if details else ""
        lines.append(f"- {timestamp} | {action_key} | actor={actor_user_id or '-'}{suffix}")
    return "\n".join(lines)


def _automation_templates_text(templates) -> str:
    lines = ["⚙️ Automation templates", ""]
    for item in templates:
        lines.append(f"- {item.name}")
        lines.append(f"  {item.description}")
    lines.append("")
    lines.append("Choose a template below to create or refresh a rule.")
    return "\n".join(lines)


def _report_action_text(action: str, bundle) -> str:
    title_map = {
        "Daily": "📅 Daily report",
        "Weekly": "📈 Weekly report",
        "Export": "📦 Export report",
    }
    body_map = {
        "Daily": bundle.daily_text,
        "Weekly": bundle.weekly_text,
        "Export": bundle.export_text,
    }
    return f"{title_map[action]}\n\n{body_map[action]}"


def _automation_rules_text(records) -> str:
    if not records:
        return (
            "⚙️ Automation rules\n\n"
            "No automation rules created yet.\n"
            "Next: open `⚙️ More -> ⚙️ Automation` and create your first rule."
        )

    lines = ["⚙️ Automation rules", ""]
    for item in records:
        next_run = item.next_run_at.strftime("%Y-%m-%d %H:%M") if item.next_run_at else "Not scheduled"
        lines.append(f"- #{item.id} {item.template_name} | {item.status} | next: {next_run}")
    return "\n".join(lines)


def _automation_rule_detail_text(record) -> str:
    last_run = record.last_run_at.strftime("%Y-%m-%d %H:%M") if record.last_run_at else "Never"
    next_run = record.next_run_at.strftime("%Y-%m-%d %H:%M") if record.next_run_at else "Not scheduled"
    return (
        f"⚙️ {record.template_name}\n\n"
        f"Template: {record.template_key}\n"
        f"Schedule: {record.schedule_key}\n"
        f"Status: {record.status}\n"
        f"Last run: {last_run}\n"
        f"Next run: {next_run}"
    )


def _group_moderation_picker_text(records) -> str:
    if not records:
        return (
            "🛡️ Group moderation\n\n"
            "No active groups found for moderation yet.\n"
            "Next: allow a group from `✅ Review`, then come back here."
        )

    return (
        "🛡️ Group moderation\n\n"
        f"Active groups: {len(records)}\n\n"
        "Choose a group to open lock, unlock, and live status controls."
    )


def _group_warning_picker_text(records) -> str:
    if not records:
        return (
            "⚠️ Group warnings\n\n"
            "No active groups are ready for warnings yet.\n"
            "Next: allow a group first, then warning tools will appear here."
        )

    return (
        "⚠️ Group warnings\n\n"
        f"Active groups: {len(records)}\n\n"
        "Choose a group to inspect warning counts or reset them."
    )


def _group_filter_picker_text(records) -> str:
    if not records:
        return (
            "🧹 Group filters\n\n"
            "No active groups are ready for protection filters yet.\n"
            "Next: allow a group first, then turn filters on here."
        )

    return (
        "🧹 Group filters\n\n"
        f"Active groups: {len(records)}\n\n"
        "Choose a group to toggle anti-link and bad-word protection."
    )


def _group_welcome_picker_text(records) -> str:
    if not records:
        return (
            "👋 Group welcome and logs\n\n"
            "No active groups are ready for welcome settings yet.\n"
            "Next: allow a group first, then set welcome and join logs here."
        )

    return (
        "👋 Group welcome and logs\n\n"
        f"Active groups: {len(records)}\n\n"
        "Choose a group to control welcome messages and join/leave logs."
    )


def _entity_list_text(section: str, items: list[str], offset: int = 0, page_size: int = 12) -> str:
    plural = "channels" if section == "Channels" else "groups"
    emoji = "📢" if section == "Channels" else "👥"
    if not items:
        return (
            f"{emoji} Managed {plural}\n\n"
            f"No managed {plural} found yet.\n"
            "Next: add one or approve a pending one first."
        )
    return (
        f"{emoji} Managed {plural}\n\n"
        f"Total: {len(items)}\n\n"
        f"Showing: {offset + 1}-{min(len(items), offset + page_size)}\n\n"
        "Current list:\n\n"
        + "\n".join(items[offset : offset + page_size])
        + (f"\n... and {len(items) - (offset + page_size)} more" if len(items) > offset + page_size else "")
        + "\n\nTip: check ✅ Review if something is still waiting for approval."
    )


def _review_text(section: str, record_id: int, identifier: str, title: str | None, status: str) -> str:
    label = "channel" if section == "Channels" else "group"
    details = [
        f"✅ Review {label}",
        "",
        f"ID: {record_id}",
        f"Identifier: {identifier}",
        f"Status: {status}",
    ]
    if title:
        details.insert(3, f"Title: {title}")
    details.extend(["", "Choose Allow, Ignore, or Block below."])
    return "\n".join(details)


def _pending_entities_text(section: str, count: int) -> str:
    emoji = "📢" if section == "Channels" else "👥"
    label = "channels" if section == "Channels" else "groups"
    return (
        f"{emoji} Pending {label}\n\n"
        f"Pending items: {count}\n\n"
        "Tap an item to review it."
    )


def _post_confirm_text(pending_post) -> str:
    label = pending_post.channel_title or pending_post.channel_identifier
    content_type = "media" if pending_post.draft_media_path else "text"
    preview = pending_post.draft_message_text or "-"
    if preview == MEDIA_ONLY_SENTINEL:
        preview = "[media only]"
    if len(preview) > 120:
        preview = preview[:117] + "..."
    media_name = pending_post.draft_media_name or "-"
    return (
        "✅ Confirm post\n\n"
        f"Channel: {label}\n"
        f"Content type: {content_type}\n"
        f"Media: {media_name}\n"
        f"Preview: {preview}\n\n"
        "Confirm to publish now, or cancel."
    )


def _broadcast_confirm_text(pending_broadcast) -> str:
    content_type = "media" if pending_broadcast.draft_media_path else "text"
    preview = pending_broadcast.draft_message_text or "-"
    if preview == MEDIA_ONLY_SENTINEL:
        preview = "[media only]"
    if len(preview) > 120:
        preview = preview[:117] + "..."
    media_name = pending_broadcast.draft_media_name or "-"
    return (
        "✅ Confirm broadcast\n\n"
        f"Targets: {len(pending_broadcast.targets)} active channels\n"
        f"Content type: {content_type}\n"
        f"Media: {media_name}\n"
        f"Preview: {preview}\n\n"
        "Confirm to send now, or cancel."
    )


async def _safe_edit_or_reply(callback: CallbackQuery, text: str, reply_markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


async def _verify_bot_chat_access(bot, section: str, identifier: str) -> tuple[bool, str]:
    try:
        chat = await bot.get_chat(identifier)
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat.id, bot_user.id)
    except TelegramBadRequest as exc:
        return False, f"Verification failed: {exc.message}"

    if member.status not in {"administrator", "creator"}:
        return False, f"Bot is not an admin in this {section[:-1].lower()}."

    if section == "Channels" and not getattr(member, "can_post_messages", True):
        return False, "Bot is admin, but posting permission is missing."

    if section == "Groups" and getattr(chat, "type", None) not in {"group", "supergroup"}:
        return False, "This chat is not a valid group."

    return True, "Verified"


async def _get_group_moderation_state(bot, identifier: str) -> tuple[bool, str]:
    try:
        chat = await bot.get_chat(identifier)
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat.id, bot_user.id)
    except TelegramBadRequest as exc:
        return False, f"Verification failed: {exc.message}"

    if member.status not in {"administrator", "creator"}:
        return False, "Bot is no longer an admin in this group."

    if getattr(chat, "type", None) not in {"group", "supergroup"}:
        return False, "This chat is not a valid group."

    if not getattr(member, "can_restrict_members", False) and member.status != "creator":
        return False, "Bot is admin, but restrict permission is missing."

    permissions = getattr(chat, "permissions", None)
    is_locked = permissions is not None and getattr(permissions, "can_send_messages", None) is False
    status = "Locked" if is_locked else "Open"
    title = getattr(chat, "title", None) or identifier
    return True, (
        f"{title}\n\n"
        f"Identifier: {_chat_identifier(chat)}\n"
        f"Live status: {status}\n"
        f"Bot role: {member.status}\n"
        "Use the controls below to lock or unlock member messaging."
    )


def _unlock_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )


def _locked_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_invite_users=False,
    )


def _build_member_label(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name


def _warning_group_key(record) -> str:
    return record.chat_identifier.replace("@", "u_")


def _warning_panel_text(group_label: str, entries) -> str:
    if not entries:
        return (
            f"{group_label}\n\n"
            "No warnings recorded yet.\n\n"
            "Next: in the group, admins can reply with /warn, /unwarn, or /warnings."
        )

    lines = [group_label, "", "Warning leaderboard", ""]
    for entry in entries:
        lines.append(f"- {entry.label} -> {entry.count}")
    lines.append("")
    lines.append("In the group, admins can reply with /warn, /unwarn, or /warnings.")
    return "\n".join(lines)


def _filter_panel_text(group_label: str, state) -> str:
    anti_link = "ON" if state.anti_link_enabled else "OFF"
    bad_word = "ON" if state.bad_word_enabled else "OFF"
    custom = ", ".join(state.custom_bad_words[:12]) if state.custom_bad_words else "None"
    return (
        f"{group_label}\n\n"
        f"Anti-link: {anti_link}\n"
        f"Bad-word filter: {bad_word}\n"
        f"Custom bad words: {custom}\n\n"
        "In the group, admins can use:\n"
        "/addbadword <word>\n"
        "/removebadword <word>\n"
        "/badwords"
    )


def _welcome_panel_text(group_label: str, state) -> str:
    welcome = "ON" if state.welcome_enabled else "OFF"
    logs = "ON" if state.join_log_enabled else "OFF"
    template = state.welcome_template or "Welcome {member} to {group}."
    return (
        f"{group_label}\n\n"
        f"Welcome messages: {welcome}\n"
        f"Join/leave logs: {logs}\n"
        f"Template: {template}\n\n"
        "In the group, admins can use:\n"
        "/setwelcome <text>\n"
        "/showwelcome\n"
        "Available placeholders: {member}, {group}"
    )


async def _resolve_active_group_record(entity_service: ManagedEntityService, chat) -> object | None:
    records = await entity_service.list_groups()
    username_identifier = f"@{chat.username}" if getattr(chat, "username", None) else None
    for record in records:
        if record.chat_identifier == str(chat.id):
            return record
        if username_identifier and record.chat_identifier == username_identifier:
            return record
    return None


async def _is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramBadRequest:
        return False
    return member.status in {"administrator", "creator"}


def _chat_identifier(chat) -> str:
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    return str(chat.id)


def _chat_section(chat_type: str) -> str | None:
    if chat_type == "channel":
        return "Channels"
    if chat_type in {"group", "supergroup"}:
        return "Groups"
    return None


def register_navigation_handlers(app_context: AppContext) -> Router:
    access_service = AccessService(app_context)
    redis_client = build_redis_client(app_context.settings)
    entity_service = ManagedEntityService(app_context, redis_client=redis_client)
    bot_service = ManagedBotService(app_context, redis_client=redis_client)
    automation_service = AutomationService(app_context)
    posting_service = PostingService(redis_client=redis_client)
    report_service = ReportService(app_context, redis_client=redis_client)
    role_service = RoleManagementService(app_context)
    schedule_service = ScheduleService(app_context, redis_client=redis_client)
    target_preferences_service = TargetPreferencesService(redis_client=redis_client)
    ui_preferences_service = UiPreferencesService(redis_client=redis_client)
    facebook_promo_service = FacebookPromoAIService(
        redis_client=redis_client,
        graph_api_enabled=app_context.settings.facebook_promo_graph_api_enabled,
        graph_version=app_context.settings.facebook_graph_version,
        gemini_api_key=app_context.settings.gemini_api_key,
        gemini_text_model=app_context.settings.gemini_text_model,
        gemini_text_fallback_model=app_context.settings.gemini_text_fallback_model,
        alibaba_api_key=app_context.settings.alibaba_api_key,
        alibaba_image_api_enabled=app_context.settings.alibaba_image_api_enabled,
        alibaba_image_dry_run=app_context.settings.alibaba_image_dry_run,
        alibaba_image_admin_live_only=app_context.settings.alibaba_image_admin_live_only,
        alibaba_image_base_url=app_context.settings.alibaba_image_base_url,
        alibaba_free_monthly_image_cap=app_context.settings.alibaba_free_monthly_image_cap,
        alibaba_paid_monthly_image_cap=app_context.settings.alibaba_paid_monthly_image_cap,
        alibaba_global_monthly_image_cap=app_context.settings.alibaba_global_monthly_image_cap,
    )
    warning_service = WarningService(redis_client=redis_client)
    filter_service = GroupFilterService(redis_client=redis_client)
    group_event_service = GroupEventService(redis_client=redis_client)

    async def render_home_panel_text(user_id: int) -> str:
        ui_mode = await ui_preferences_service.get_mode(user_id)
        pending_channels = await entity_service.list_channels_by_status("PENDING")
        pending_groups = await entity_service.list_groups_by_status("PENDING")
        failed_schedules = await schedule_service.list_failed()
        active_channels = await entity_service.list_channels()
        active_groups = await entity_service.list_groups()
        bots = await bot_service.list_bots()
        bot_issues = len([item for item in bots if item.status not in {"ONLINE", "OK"}])
        if not active_channels and not active_groups and not bots:
            return (
                "🏠 Home\n\n"
                f"Mode: {ui_mode.title()}\n\n"
                "👋 Setup looks empty right now.\n\n"
                "Best next steps:\n"
                "1. ➕ Add your first channel\n"
                "2. 📝 Make a quick post\n"
                "3. ✅ Review new items when the bot joins chats\n\n"
                "Use the starter buttons below."
            )
        return (
            "🏠 Home\n\n"
            f"Mode: {ui_mode.title()}\n"
            f"⏳ Pending review: {len(pending_channels) + len(pending_groups)}\n"
            f"❌ Failed schedules: {len(failed_schedules)}\n"
            f"📢 Active channels: {len(active_channels)}\n"
            f"🤖 Bot issues: {bot_issues}\n\n"
            "Choose a shortcut below."
        )

    async def render_review_hub_text() -> str:
        pending_channels = await entity_service.list_channels_by_status("PENDING")
        pending_groups = await entity_service.list_groups_by_status("PENDING")
        return (
            "✅ Review new items\n\n"
            f"📢 Pending channels: {len(pending_channels)}\n"
            f"👥 Pending groups: {len(pending_groups)}\n\n"
            "Pick what you want to review first."
        )

    async def is_onboarding_state() -> bool:
        active_channels = await entity_service.list_channels()
        active_groups = await entity_service.list_groups()
        bots = await bot_service.list_bots()
        return not active_channels and not active_groups and not bots

    async def ranked_channel_items(user_id: int) -> list[tuple[int, str, str | None, bool, bool]]:
        records = await entity_service.list_channels()
        ranked = await target_preferences_service.rank_channels(user_id, records)
        return [
            (record.id, record.chat_identifier, record.title, is_favorite, is_recent)
            for record, is_favorite, is_recent in ranked
            if record.id is not None
        ]

    async def quick_channel_items(user_id: int) -> list[tuple[int, str, str | None, bool, bool]]:
        records = await entity_service.list_channels()
        quick = await target_preferences_service.quick_channels(user_id, records, limit=3)
        return [
            (record.id, record.chat_identifier, record.title, is_favorite, is_recent)
            for record, is_favorite, is_recent in quick
            if record.id is not None
        ]

    async def open_post_picker(message: Message) -> None:
        records = await entity_service.list_channels()
        if not records:
            await message.answer(
                "No active channels yet.\n\nNext: add one or review pending items first.",
                reply_markup=build_empty_recovery_keyboard("post"),
            )
            return
        ranked_items = await ranked_channel_items(message.from_user.id)
        quick_items = await quick_channel_items(message.from_user.id)
        await message.answer(
            _channel_picker_text("post", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in ranked_items]),
            reply_markup=build_channel_post_keyboard(quick_items + ranked_items, "all"),
        )

    async def open_schedule_picker(message: Message) -> None:
        records = await entity_service.list_channels()
        if not records:
            await message.answer(
                "No active channels yet.\n\nNext: add one or review pending items first.",
                reply_markup=build_empty_recovery_keyboard("schedule"),
            )
            return
        ranked_items = await ranked_channel_items(message.from_user.id)
        quick_items = await quick_channel_items(message.from_user.id)
        await message.answer(
            "⏰ Choose an active channel first.\n\nAfter that, I will ask what kind of schedule you want.\nUse /schedule_list to review saved schedules.",
            reply_markup=build_channel_schedule_keyboard(quick_items + ranked_items, "all"),
        )

    async def open_broadcast_picker(message: Message) -> None:
        records = await entity_service.list_channels()
        if not records:
            await message.answer(
                "No active channels yet.\n\nNext: add one or review pending items first.",
                reply_markup=build_empty_recovery_keyboard("broadcast"),
            )
            return
        selection = await posting_service.get_broadcast_selection(message.from_user.id)
        ranked_items = await ranked_channel_items(message.from_user.id)
        quick_items = await quick_channel_items(message.from_user.id)
        await message.answer(
            _broadcast_select_text(len(records), len(selection.selected_ids)),
            reply_markup=build_broadcast_select_keyboard(quick_items + ranked_items, set(selection.selected_ids), "all"),
        )

    async def render_section_overview(section: str, user_id: int) -> str:
        if section == "Home":
            return await render_home_panel_text(user_id)
        if section == "Quick":
            return _section_text("Create")
        if section == "Create":
            return (
                "⚡ Create\n\n"
                "Choose what you want to send or create right now."
            )
        if section == "Review":
            pending_channels = await entity_service.list_channels_by_status("PENDING")
            pending_groups = await entity_service.list_groups_by_status("PENDING")
            schedules = await schedule_service.list_manageable()
            return (
                "✅ Review\n\n"
                f"📢 Pending channels: {len(pending_channels)}\n"
                f"👥 Pending groups: {len(pending_groups)}\n"
                f"⏰ Schedules: {len(schedules)}\n\n"
                "Pick what needs your attention."
            )
        if section == "Status":
            active_channels = await entity_service.list_channels()
            active_groups = await entity_service.list_groups()
            bots = await bot_service.list_bots()
            return (
                "📊 Status\n\n"
                f"📢 Channels: {len(active_channels)}\n"
                f"👥 Groups: {len(active_groups)}\n"
                f"🤖 Bots: {len(bots)}\n\n"
                "Pick what you want to inspect."
            )
        if section == "More":
            ui_mode = await ui_preferences_service.get_mode(user_id)
            return (
                "⚙️ More\n\n"
                f"Current mode: {ui_mode.title()}\n\n"
                "Advanced tools and deeper sections live here."
            )
        if section == "Automation":
            promo_profile = await facebook_promo_service.get_profile(user_id)
            status_label = "Active" if promo_profile.status == "ACTIVE" else "Inactive"
            access_ok = bool(promo_profile.page_id and promo_profile.page_access_token)
            return (
                "🧠 Automation\n\n"
                f"Facebook Promo AI: {status_label}\n"
                f"Page access: {'Connected' if access_ok else 'Not set'}\n\n"
                "Pick an action below."
            )
        if section == "Channels":
            active = await entity_service.list_channels()
            pending = await entity_service.list_channels_by_status("PENDING")
            schedules = await schedule_service.list_manageable()
            return (
                "📢 Channel Center\n\n"
                f"✅ Active: {len(active)}\n"
                f"⏳ Pending: {len(pending)}\n"
                f"⏰ Schedules: {len(schedules)}\n\n"
                "Pick one to continue."
            )
        if section == "Groups":
            active = await entity_service.list_groups()
            pending = await entity_service.list_groups_by_status("PENDING")
            return (
                "👥 Group Center\n\n"
                f"✅ Active: {len(active)}\n"
                f"⏳ Pending: {len(pending)}\n\n"
                "Pick one to continue."
            )
        if section == "Bots":
            bots = await bot_service.list_bots()
            healthy = len([item for item in bots if item.status in {"ONLINE", "OK"}])
            return (
                "🤖 Bot Center\n\n"
                f"📦 Tracked bots: {len(bots)}\n"
                f"🟢 Healthy: {healthy}\n\n"
                "Pick one to continue."
            )
        if section == "Reports":
            return (
                "📊 Reports\n\n"
                "Open quick summaries, weekly overview, or export-ready snapshots."
            )
        return _section_text(section)

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer(
                "This bot is for approved admins only right now.\n\nIf you need access, ask an owner to approve you first.",
            )
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="BOT_START",
            target_type="USER",
            target_id=str(message.from_user.id),
            details=f"owner={is_owner(profile)}",
        )
        ui_mode = await ui_preferences_service.get_mode(message.from_user.id)
        allowed_sections = get_visible_main_menu_keys(profile, _menu_keys_for_mode(ui_mode))
        await message.answer(
            "👋 Ready. Pick a section below to start.",
            reply_markup=build_main_menu_keyboard(allowed_sections),
        )

    @router.message(Command("cancel"))
    async def cancel_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer("This bot is not available for your role yet.")
            return

        pending_entity = await entity_service.get_pending_action(message.from_user.id)
        pending_bot = await bot_service.get_pending_action(message.from_user.id)
        pending_post = await posting_service.get_pending_post(message.from_user.id)
        pending_broadcast = await posting_service.get_pending_broadcast(message.from_user.id)
        pending_schedule = await schedule_service.get_pending(message.from_user.id)
        pending_facebook_promo = await facebook_promo_service.get_pending_action(message.from_user.id)
        pending_search = await target_preferences_service.get_search_context(message.from_user.id)

        if not any([pending_entity, pending_bot, pending_post, pending_broadcast, pending_schedule, pending_facebook_promo, pending_search]):
            await message.answer(
                "There is no active draft right now.\n\nYou can start a new action from the menu below.",
                reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(message.from_user.id)),
            )
            return

        await entity_service.clear_pending_action(message.from_user.id)
        await bot_service.clear_pending_action(message.from_user.id)
        await posting_service.clear_pending_post(message.from_user.id)
        await posting_service.clear_pending_broadcast(message.from_user.id)
        await schedule_service.clear_pending(message.from_user.id)
        await facebook_promo_service.clear_pending_action(message.from_user.id)
        await target_preferences_service.clear_search_context(message.from_user.id)

        await message.answer(
            "✅ Current flow canceled.\n\nYou can start again from the menu below.",
            reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(message.from_user.id)),
        )

    @router.message(F.text.in_(MAIN_MENU_LABELS))
    async def section_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer("This action is not available for your role right now.")
            return

        section = normalize_main_menu_label(message.text)
        if not section:
            return
        if not can_open_section(profile, section):
            await message.answer("This section is not available for your role right now.")
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="OPEN_SECTION",
            target_type="SECTION",
            target_id=section,
        )
        await message.answer(
            await render_section_overview(section, message.from_user.id),
            reply_markup=build_section_actions_keyboard(section),
        )

    @router.message(F.text & ~F.text.startswith("/"))
    async def pending_entity_input_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            return

        pending_entity_state = await entity_service.get_pending_action(message.from_user.id)
        pending_bot_state = await bot_service.get_pending_action(message.from_user.id)
        pending_post_state = await posting_service.get_pending_post(message.from_user.id)
        pending_broadcast_state = await posting_service.get_pending_broadcast(message.from_user.id)
        pending_schedule_state = await schedule_service.get_pending(message.from_user.id)
        pending_facebook_promo_state = await facebook_promo_service.get_pending_action(message.from_user.id)
        pending_search = await target_preferences_service.get_search_context(message.from_user.id)
        if pending_search:
            await target_preferences_service.clear_search_context(message.from_user.id)
            ranked_items = await ranked_channel_items(message.from_user.id)
            filtered_items = _search_ranked_channel_items(ranked_items, message.text)
            if not filtered_items:
                await message.answer(
                    _search_empty_text(pending_search, message.text),
                    reply_markup=build_search_recovery_keyboard(pending_search),
                )
                return

            if pending_search == "post":
                await message.answer(
                    _search_results_text("post", message.text, filtered_items),
                    reply_markup=build_channel_post_keyboard(filtered_items, "all"),
                )
                return

            if pending_search == "schedule":
                await message.answer(
                    _search_results_text("schedule", message.text, filtered_items) + "\n\nUse /schedule_list to review saved schedules.",
                    reply_markup=build_channel_schedule_keyboard(filtered_items, "all"),
                )
                return

            if pending_search == "broadcast":
                selection = await posting_service.get_broadcast_selection(message.from_user.id)
                all_records = await entity_service.list_channels()
                await message.answer(
                    _search_results_text("broadcast", message.text, filtered_items)
                    + f"\n\nSelected targets: {len(selection.selected_ids)} of {len(all_records)}",
                    reply_markup=build_broadcast_select_keyboard(filtered_items, set(selection.selected_ids), "all"),
                )
                return

        if not any([pending_entity_state, pending_bot_state, pending_post_state, pending_broadcast_state, pending_schedule_state, pending_facebook_promo_state]):
            intent = parse_natural_intent(message.text)
            if intent:
                intent_type, intent_value = intent
                if intent_type == "section":
                    await message.answer(
                        await render_section_overview(intent_value, message.from_user.id),
                        reply_markup=build_section_actions_keyboard(intent_value),
                    )
                    return

                if intent_value == "post":
                    await open_post_picker(message)
                    return
                if intent_value == "schedule":
                    await open_schedule_picker(message)
                    return
                if intent_value == "broadcast":
                    await open_broadcast_picker(message)
                    return
                if intent_value == "review":
                    await message.answer(
                        await render_review_hub_text(),
                        reply_markup=build_review_hub_keyboard(),
                    )
                    return
                if intent_value == "alerts":
                    reports = await report_service.build_reports()
                    await message.answer(
                        _report_action_text("Daily", reports),
                        reply_markup=build_section_actions_keyboard("Reports"),
                    )
                    return

            await message.answer(
                build_intent_fallback_text(message.text),
                reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(message.from_user.id)),
            )
            return

        pending_facebook_promo = await facebook_promo_service.get_pending_action(message.from_user.id)
        if pending_facebook_promo:
            if pending_facebook_promo.stage == "await_request":
                await facebook_promo_service.save_user_request(message.from_user.id, pending_facebook_promo, message.text)
                refreshed = await facebook_promo_service.get_pending_action(message.from_user.id)
                await message.answer(
                    _facebook_promo_goal_prompt(refreshed),
                    reply_markup=build_facebook_promo_goal_keyboard(),
                )
                return

            if pending_facebook_promo.stage == "await_page_id":
                profile_record = await facebook_promo_service.set_page_id(message.from_user.id, message.text)
                await facebook_promo_service.clear_pending_action(message.from_user.id)
                await message.answer(
                    "✅ Page ID saved.\n\nNext, save the Page access token.",
                    reply_markup=build_facebook_promo_access_v2_keyboard(
                        bool(profile_record.page_id),
                        bool(profile_record.page_access_token),
                    ),
                )
                return

            if pending_facebook_promo.stage == "await_page_token":
                profile_record = await facebook_promo_service.set_page_access_token(message.from_user.id, message.text)
                await facebook_promo_service.clear_pending_action(message.from_user.id)
                token_message_removed = True
                try:
                    await message.delete()
                except TelegramBadRequest:
                    token_message_removed = False
                await message.answer(
                    "✅ Access token saved.\n\nNow tell the agent about your brand, audience, and promo style.",
                    reply_markup=build_facebook_promo_access_v2_keyboard(
                        bool(profile_record.page_id),
                        bool(profile_record.page_access_token),
                    ),
                )
                if not token_message_removed:
                    await message.answer("Security note: I could not delete the token message automatically. Please delete it from chat if possible.")
                return

            if pending_facebook_promo.stage == "await_brand_notes":
                profile_record = await facebook_promo_service.set_brand_notes(message.from_user.id, message.text)
                await facebook_promo_service.clear_pending_action(message.from_user.id)
                await message.answer(
                    "✅ Brand notes saved.\n\nGood. Now tell AI how you want promo tasks to be handled.",
                    reply_markup=_facebook_promo_hub_keyboard(profile_record),
                )
                return

            if pending_facebook_promo.stage == "await_strategy_brief":
                profile_record = await facebook_promo_service.update_strategy(message.from_user.id, message.text)
                await facebook_promo_service.clear_pending_action(message.from_user.id)
                await message.answer(
                    "✅ AI brief updated.\n\nI saved your instruction as working memory. Later this agent will ask better follow-up questions before writing or posting anything.",
                    reply_markup=_facebook_promo_hub_keyboard(profile_record),
                )
                await message.answer(_facebook_promo_working_plan_text(profile_record))
                return

            if pending_facebook_promo.stage == "await_topic":
                await facebook_promo_service.save_topic(message.from_user.id, pending_facebook_promo, message.text)
                refreshed = await facebook_promo_service.get_pending_action(message.from_user.id)
                await message.answer(_facebook_promo_audience_prompt(refreshed))
                return

            if pending_facebook_promo.stage == "await_audience":
                await facebook_promo_service.save_audience(message.from_user.id, pending_facebook_promo, message.text)
                refreshed = await facebook_promo_service.get_pending_action(message.from_user.id)
                await message.answer(
                    _facebook_promo_image_prompt(refreshed),
                    reply_markup=build_facebook_promo_image_keyboard(),
                )
                return

            if pending_facebook_promo.stage == "await_angle":
                recommendations = facebook_promo_service.generate_recommendations(pending_facebook_promo)
                await message.answer(
                    "Pick one of the recommended directions below to continue.",
                    reply_markup=build_facebook_promo_recommendation_keyboard(
                        [(item.key, item.title) for item in recommendations]
                    ),
                )
                return

            if pending_facebook_promo.stage == "await_plan_feedback":
                await facebook_promo_service.set_plan_feedback(message.from_user.id, pending_facebook_promo, message.text)
                refreshed = await facebook_promo_service.get_pending_action(message.from_user.id)
                plan = facebook_promo_service.generate_strategy_plan(refreshed)
                await message.answer(
                    _facebook_promo_strategy_plan_text(refreshed, plan),
                    reply_markup=build_facebook_promo_plan_keyboard(),
                )
                return

            if pending_facebook_promo.stage == "await_draft_feedback":
                draft = await facebook_promo_service.refine_saved_draft(message.from_user.id, message.text)
                await facebook_promo_service.clear_pending_action(message.from_user.id)
                if not draft:
                    await message.answer("I could not find a saved draft to refine yet.")
                    return
                await message.answer(
                    _facebook_promo_draft_text(draft),
                    reply_markup=build_facebook_promo_draft_v4_keyboard(),
                )
                return

        pending_broadcast = await posting_service.pop_pending_broadcast(message.from_user.id)
        if pending_broadcast:
            if pending_broadcast.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this broadcast.",
                    reply_markup=build_post_confirm_keyboard("broadcast"),
                )
                return

            await posting_service.set_broadcast_draft(
                message.from_user.id,
                pending_broadcast,
                message.text,
            )
            draft_broadcast = await posting_service.get_pending_broadcast(message.from_user.id)
            await message.answer(
                _broadcast_confirm_text(draft_broadcast),
                reply_markup=build_post_confirm_keyboard("broadcast"),
            )
            return

        pending_post = await posting_service.pop_pending_post(message.from_user.id)
        if pending_post:
            if pending_post.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this post.",
                    reply_markup=build_post_confirm_keyboard("post"),
                )
                return

            await posting_service.set_post_draft(
                message.from_user.id,
                pending_post,
                message.text,
            )
            draft_post = await posting_service.get_pending_post(message.from_user.id)
            await message.answer(
                _post_confirm_text(draft_post),
                reply_markup=build_post_confirm_keyboard("post"),
            )
            return

        pending_bot = await bot_service.pop_pending_action(message.from_user.id)
        if pending_bot:
            (
                bot_username,
                display_name,
                healthcheck_url,
                action_url,
                action_method,
                action_payload_template,
                action_auth_header,
                action_secret,
                notes,
            ) = bot_service.parse_bot_input(message.text)
            if not bot_username:
                await message.answer("A valid bot username is required. Example: @my_bot")
                return

            record = await bot_service.add_bot(
                bot_username,
                display_name,
                healthcheck_url,
                action_url,
                action_method,
                action_payload_template,
                None,
                action_auth_header,
                action_secret,
                notes,
                profile.user.id,
            )
            if not record:
                await message.answer("Bot registry is not available yet.")
                return

            await access_service.record_event(
                actor_user_id=profile.user.id,
                action_key="ADD_MANAGED_BOT",
                target_type="BOT",
                target_id=record.bot_username,
                details=record.display_name,
            )
            await message.answer(
                f"Saved bot: {record.bot_username}" + (f" ({record.display_name})" if record.display_name else ""),
                reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(message.from_user.id)),
            )
            await message.answer(
                "Next, you can check this bot or add another one.",
                reply_markup=build_success_next_keyboard("bot_saved"),
            )
            return

        pending_schedule = await schedule_service.get_pending(message.from_user.id)
        if pending_schedule:
            if pending_schedule.stage == "await_time":
                try:
                    parsed_schedule = _resolve_schedule_spec_for_pending(
                        pending_schedule,
                        message.text.strip(),
                        schedule_service.parse_schedule_time,
                    )
                except ValueError:
                    await message.answer(_schedule_time_prompt_for_mode(
                        pending_schedule.channel_identifier,
                        pending_schedule.channel_title,
                        pending_schedule.schedule_mode,
                    ), reply_markup=build_schedule_time_shortcuts_keyboard(
                        _schedule_shortcut_options(pending_schedule.schedule_mode)
                    ))
                    return

                normalized_schedule = parsed_schedule.scheduled_for.strftime("%Y-%m-%d %H:%M")
                await schedule_service.advance_to_message(
                    message.from_user.id,
                    pending_schedule,
                    normalized_schedule,
                    parsed_schedule.recurrence_key,
                )
                await message.answer(
                    _schedule_message_prompt(
                        pending_schedule.channel_identifier,
                        pending_schedule.channel_title,
                        normalized_schedule,
                    )
                )
                return

            if pending_schedule.stage == "await_message":
                await schedule_service.set_draft_content(
                    message.from_user.id,
                    pending_schedule,
                    message.text,
                )
                await message.answer(
                    _schedule_confirm_text(await schedule_service.get_pending(message.from_user.id)),
                    reply_markup=build_schedule_confirm_keyboard(),
                )
                return

            if pending_schedule.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below to confirm this schedule, edit the time, or cancel it.",
                    reply_markup=build_schedule_confirm_keyboard(),
                )
                return

            await message.answer("This schedule is waiting for content.")
            return

    @router.message(F.chat.type == "private", F.photo)
    @router.message(F.chat.type == "private", F.video)
    @router.message(F.chat.type == "private", F.document)
    async def pending_media_input_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            return

        if not message_has_supported_media(message):
            return

        pending_broadcast = await posting_service.pop_pending_broadcast(message.from_user.id)
        if pending_broadcast:
            if pending_broadcast.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this broadcast.",
                    reply_markup=build_post_confirm_keyboard("broadcast"),
                )
                return

            media_path, media_name, media_type = await store_message_media(message.bot, message)
            message_text = extract_message_text(message) or MEDIA_ONLY_SENTINEL
            await posting_service.set_broadcast_draft(
                message.from_user.id,
                pending_broadcast,
                message_text,
                media_path=media_path,
                media_name=media_name,
                media_type=media_type,
            )
            draft_broadcast = await posting_service.get_pending_broadcast(message.from_user.id)
            await message.answer(
                _broadcast_confirm_text(draft_broadcast),
                reply_markup=build_post_confirm_keyboard("broadcast"),
            )
            return

        pending_post = await posting_service.pop_pending_post(message.from_user.id)
        if pending_post:
            if pending_post.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this post.",
                    reply_markup=build_post_confirm_keyboard("post"),
                )
                return

            media_path, media_name, media_type = await store_message_media(message.bot, message)
            message_text = extract_message_text(message) or MEDIA_ONLY_SENTINEL
            await posting_service.set_post_draft(
                message.from_user.id,
                pending_post,
                message_text,
                media_path=media_path,
                media_name=media_name,
                media_type=media_type,
            )
            draft_post = await posting_service.get_pending_post(message.from_user.id)
            await message.answer(
                _post_confirm_text(draft_post),
                reply_markup=build_post_confirm_keyboard("post"),
            )
            return

        pending_schedule = await schedule_service.get_pending(message.from_user.id)
        if pending_schedule:
            if pending_schedule.stage == "await_time":
                await message.answer(
                    "Send the schedule time first. After that, send text, photo, video, or document."
                )
                return

            if pending_schedule.stage == "await_message":
                media_path, media_name, media_type = await store_message_media(message.bot, message)
                message_text = extract_message_text(message) or MEDIA_ONLY_SENTINEL
                await schedule_service.set_draft_content(
                    message.from_user.id,
                    pending_schedule,
                    message_text,
                    media_path=media_path,
                    media_name=media_name,
                    media_type=media_type,
                )
                await message.answer(
                    _schedule_confirm_text(await schedule_service.get_pending(message.from_user.id)),
                    reply_markup=build_schedule_confirm_keyboard(),
                )
                return

            if pending_schedule.stage == "await_confirm":
                await message.answer(
                    "Use the buttons below to confirm this schedule, edit the time, or cancel it.",
                    reply_markup=build_schedule_confirm_keyboard(),
                )
                return

            await message.answer("This schedule is waiting for a valid content step.")
            return

    @router.message(
        F.chat.type == "private",
        F.audio | F.voice | F.video_note | F.animation | F.sticker,
    )
    async def unsupported_private_media_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            return

        pending_post = await posting_service.get_pending_post(message.from_user.id)
        pending_broadcast = await posting_service.get_pending_broadcast(message.from_user.id)
        pending_schedule = await schedule_service.get_pending(message.from_user.id)
        if not any([pending_post, pending_broadcast, pending_schedule]):
            return

        if pending_post and pending_post.stage == "await_confirm":
            await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this post.",
                reply_markup=build_post_confirm_keyboard("post"),
            )
            return

        if pending_broadcast and pending_broadcast.stage == "await_confirm":
            await message.answer(
                    "Use the buttons below when you're ready to confirm or cancel this broadcast.",
                reply_markup=build_post_confirm_keyboard("broadcast"),
            )
            return

        if pending_schedule and pending_schedule.stage == "await_time":
            await message.answer(
                "This step is waiting for schedule time, not media.\n"
                "Send a time first, then send text, photo, video, or document."
            )
            return

        media_label = describe_incoming_media(message)
        await message.answer(
            f"`{media_label}` is not supported in this flow yet.\n"
            "Please send text, photo, video, or document instead."
        )

        pending_action = await entity_service.pop_pending_action(message.from_user.id)
        if not pending_action:
            return

        identifier, title = entity_service.parse_entity_input(message.text)
        if not identifier:
            await message.answer("A valid identifier is required.")
            return

        if pending_action.section == "Channels":
            record = await entity_service.add_channel(identifier, title, profile.user.id, status="ACTIVE")
            target_type = "CHANNEL"
        else:
            record = await entity_service.add_group(identifier, title, profile.user.id, status="ACTIVE")
            target_type = "GROUP"

        if not record:
            await message.answer(
                "Oracle is not configured yet. Fill the database credentials first, then try again."
            )
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key=f"ADD_{target_type}",
            target_type=target_type,
            target_id=record.chat_identifier,
            details=record.title,
        )
        await message.answer(
            f"Saved {target_type.lower()}: {record.chat_identifier}"
            + (f" ({record.title})" if record.title else ""),
            reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(message.from_user.id)),
        )
        await message.answer(
            "Nice. You can continue with one of these next steps.",
            reply_markup=build_success_next_keyboard("channel_saved" if section == "Channels" else "group_saved"),
        )

    @router.callback_query(F.data == "nav:home")
    async def home_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        ui_mode = await ui_preferences_service.get_mode(callback.from_user.id)
        allowed_sections = get_visible_main_menu_keys(profile, _menu_keys_for_mode(ui_mode))
        await callback.answer("Home ready")
        await _safe_edit_or_reply(callback, await render_section_overview("Home", callback.from_user.id), build_section_actions_keyboard("Home"))
        await callback.message.answer(
            "Home shortcuts are ready below.",
            reply_markup=build_main_menu_keyboard(allowed_sections),
        )

    @router.callback_query(F.data == "nav:back")
    async def back_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        ui_mode = await ui_preferences_service.get_mode(callback.from_user.id)
        allowed_sections = get_visible_main_menu_keys(profile, _menu_keys_for_mode(ui_mode))
        await callback.answer("Back to home")
        await _safe_edit_or_reply(callback, await render_section_overview("Home", callback.from_user.id), build_section_actions_keyboard("Home"))
        await callback.message.answer(
            "Home shortcuts are ready below.",
            reply_markup=build_main_menu_keyboard(allowed_sections),
        )

    @router.callback_query(F.data == "noop:list")
    async def noop_list_callback(callback: CallbackQuery) -> None:
        await callback.answer("This row is just a preview.")

    @router.callback_query(F.data.startswith("listpage:entity:"))
    async def entity_list_page_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, section, offset_raw = callback.data.split(":", maxsplit=3)
        offset = max(int(offset_raw), 0)
        records = await (entity_service.list_channels() if section == "Channels" else entity_service.list_groups())
        lines = [f"- {item.chat_identifier}" + (f" | {item.title}" if item.title else "") for item in records]
        await callback.answer("More items ready")
        await _safe_edit_or_reply(
            callback,
            _entity_list_text(section, lines, offset),
            build_entity_list_keyboard(
                section,
                [(item.id, item.chat_identifier, item.title) for item in records],
                offset,
            ),
        )

    @router.callback_query(F.data.startswith("listpage:bot:"))
    async def bot_list_page_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, kind, offset_raw = callback.data.split(":", maxsplit=3)
        offset = max(int(offset_raw), 0)
        records = await bot_service.list_bots()
        keyboard_rows = [(item.id, item.bot_username, item.display_name, item.status) for item in records]
        if kind == "status":
            text = _bot_status_picker_text(records, offset)
        elif kind == "logs":
            text = _bot_logs_picker_text(records, offset)
        else:
            text = _bot_configs_picker_text(records, offset)
        await callback.answer("More bots ready")
        await _safe_edit_or_reply(
            callback,
            text,
            build_bot_picker_keyboard(kind, keyboard_rows, offset),
        )

    @router.callback_query(F.data.startswith("section:"))
    async def action_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, section, action = callback.data.split(":", maxsplit=2)
        if not can_run_section_action(profile, section, action):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="SECTION_ACTION",
            target_type=section,
            target_id=action,
        )

        if section == "Home" and action == "Review":
            await callback.answer("Review ready")
            await _safe_edit_or_reply(
                callback,
                await render_review_hub_text(),
                build_review_hub_keyboard(),
            )
            return

        if (section == "Home" and action == "New Post") or (section == "Create" and action == "Post"):
            section = "Channels"
            action = "Post"

        if (section == "Home" and action == "New Schedule") or (section == "Create" and action == "Schedule"):
            section = "Channels"
            action = "Schedule"

        if section == "Create" and action == "Broadcast":
            section = "Broadcast"
            action = "Send All"

        if (section == "Home" and action == "Alerts") or (section == "Review" and action == "Alerts"):
            reports = await report_service.build_reports()
            await callback.answer("Alerts ready")
            await _safe_edit_or_reply(
                callback,
                _report_action_text("Daily", reports),
                build_section_actions_keyboard("Reports"),
            )
            return

        if section == "Home" and action == "More":
            await callback.answer("More tools ready")
            await _safe_edit_or_reply(
                callback,
                await render_section_overview("More", callback.from_user.id),
                build_section_actions_keyboard("More"),
            )
            return

        if section in {"Home", "More"} and action == "Mode":
            new_mode = await ui_preferences_service.toggle_mode(callback.from_user.id)
            allowed_sections = get_visible_main_menu_keys(profile, _menu_keys_for_mode(new_mode))
            source_section = "More" if section == "More" else "Home"
            await callback.answer(f"Switched to {new_mode.title()} mode")
            await _safe_edit_or_reply(
                callback,
                await render_section_overview(source_section, callback.from_user.id),
                build_section_actions_keyboard(source_section),
            )
            await callback.message.answer(
                f"🧭 Mode updated to {new_mode.title()}.\n\nSimple mode keeps things lighter. Pro mode shows more direct sections.",
                reply_markup=build_main_menu_keyboard(allowed_sections),
            )
            return

        if section == "Create" and action == "Add Channel":
            section = "Channels"
            action = "Add"

        if section == "Create" and action == "Add Group":
            section = "Groups"
            action = "Add"

        if section == "Review" and action == "Pending Channels":
            section = "Channels"
            action = "Pending"

        if section == "Review" and action == "Pending Groups":
            section = "Groups"
            action = "Pending"

        if section == "Review" and action == "Schedules":
            await callback.answer("Schedules ready")
            records = await schedule_service.list_manageable()
            labels = [
                (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
                for item in records
            ]
            await _safe_edit_or_reply(
                callback,
                _schedule_list_text(records),
                build_schedule_list_keyboard(labels) if labels else build_section_actions_keyboard("Channels"),
            )
            return

        if section == "Status" and action == "Channels":
            section = "Channels"
            action = "List"

        if section == "Status" and action == "Groups":
            section = "Groups"
            action = "List"

        if section == "Status" and action == "Bots":
            section = "Bots"
            action = "Status"

        if section == "Status" and action == "Reports":
            section = "Reports"
            action = "Daily"

        if section == "More" and action in {"Channels", "Groups", "Bots", "Automation", "Settings"}:
            await callback.answer(f"{action} ready")
            await _safe_edit_or_reply(
                callback,
                await render_section_overview(action, callback.from_user.id),
                build_section_actions_keyboard(action),
            )
            return

        if section in {"Channels", "Groups"} and action == "Add":
            await callback.answer(f"Send {section[:-1].lower()} details")
            await entity_service.set_pending_action(callback.from_user.id, section, action)
            await _safe_edit_or_reply(
                callback,
                _entity_input_prompt(section),
                build_section_actions_keyboard(section),
            )
            return

        if section == "Channels" and action == "View":
            records = await entity_service.list_channels()
            lines = [f"- {item.chat_identifier}" + (f" | {item.title}" if item.title else "") for item in records]
            await callback.answer("Channels ready")
            await _safe_edit_or_reply(
                callback,
                _entity_list_text(section, lines, 0),
                build_entity_list_keyboard(
                    section,
                    [(item.id, item.chat_identifier, item.title) for item in records],
                    0,
                ) if records else build_section_actions_keyboard(section),
            )
            return

        if section == "Channels" and action == "Pending":
            records = await entity_service.list_channels_by_status("PENDING")
            await callback.answer("Pending channels ready")
            await _safe_edit_or_reply(
                callback,
                _pending_entities_text(section, len(records)),
                build_pending_entities_keyboard(
                    section,
                    [(item.id, item.chat_identifier, item.title) for item in records],
                ) if records else build_section_actions_keyboard(section),
            )
            return

        if section == "Channels" and action == "Post":
            records = await entity_service.list_channels()
            if not records:
                await callback.answer("No active channels yet. Add one first.", show_alert=True)
                return

            ranked_items = await ranked_channel_items(callback.from_user.id)
            quick_items = await quick_channel_items(callback.from_user.id)
            await callback.answer("Select a channel")
            await _safe_edit_or_reply(
                callback,
                _channel_picker_text("post", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in ranked_items]),
                build_channel_post_keyboard(quick_items + ranked_items, "all"),
            )
            return

        if section == "Channels" and action == "Schedule":
            records = await entity_service.list_channels()
            if not records:
                await callback.answer("No active channels yet. Add one first.", show_alert=True)
                return

            ranked_items = await ranked_channel_items(callback.from_user.id)
            quick_items = await quick_channel_items(callback.from_user.id)
            await callback.answer("Select a channel")
            await _safe_edit_or_reply(
                callback,
                "⏰ Choose an active channel first.\n\nAfter that, I will ask what kind of schedule you want.\nUse /schedule_list to review saved schedules.",
                build_channel_schedule_keyboard(quick_items + ranked_items, "all"),
            )
            return

        if section == "Broadcast" and action == "Targets":
            records = await entity_service.list_channels()
            lines = [
                f"- {item.chat_identifier}" + (f" | {item.title}" if item.title else "")
                for item in records
            ]
            await callback.answer("Targets ready")
            await _safe_edit_or_reply(
                callback,
                "📤 Broadcast targets\n\n" + ("\n".join(lines) if lines else "No active channels yet."),
                build_section_actions_keyboard(section),
            )
            return

        if section == "Broadcast" and action == "Send All":
            records = await entity_service.list_channels()
            if not records:
                await callback.answer("No active channels yet. Add one first.", show_alert=True)
                return

            await posting_service.set_pending_broadcast(
                callback.from_user.id,
                [
                    {
                        "channel_identifier": item.chat_identifier,
                        "channel_title": item.title,
                    }
                    for item in records
                ],
            )
            await callback.answer("Send broadcast content")
            await _safe_edit_or_reply(
                callback,
                _broadcast_prompt(len(records)),
                build_section_actions_keyboard(section),
            )
            return

        if section == "Broadcast" and action == "Select":
            records = await entity_service.list_channels()
            if not records:
                await callback.answer("No active channels yet. Add one first.", show_alert=True)
                return

            selection = await posting_service.get_broadcast_selection(callback.from_user.id)
            ranked_items = await ranked_channel_items(callback.from_user.id)
            quick_items = await quick_channel_items(callback.from_user.id)
            await callback.answer("Select targets")
            await _safe_edit_or_reply(
                callback,
                _broadcast_select_text(len(records), len(selection.selected_ids)),
                build_broadcast_select_keyboard(
                    quick_items + ranked_items,
                    set(selection.selected_ids),
                    "all",
                ),
            )
            return

        if section == "Automation" and action == "Facebook Promo AI":
            promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
            await callback.answer("Facebook Promo AI ready")
            access_ok = bool(promo_profile.page_id and promo_profile.page_access_token)
            status_label = "Active" if promo_profile.status == "ACTIVE" else "Inactive"
            await _safe_edit_or_reply(
                callback,
                f"🧠 Facebook Promo AI\n\nStatus: {status_label}\nPage access: {'Connected' if access_ok else 'Not set'}\n\nChat with AI to create promos, update brief, or manage campaigns.",
                _facebook_promo_hub_keyboard(promo_profile),
            )
            return

        if section == "Reports" and action in {"Daily", "Weekly", "Export"}:
            bundle = await report_service.build_reports()
            mapping = {
                "Daily": _report_action_text("Daily", bundle),
                "Weekly": _report_action_text("Weekly", bundle),
                "Export": _report_action_text("Export", bundle),
            }
            await callback.answer(f"{action} report ready")
            await _safe_edit_or_reply(
                callback,
                mapping[action],
                build_section_actions_keyboard(section),
            )
            return

        if section == "Bots" and action == "Status":
            records = await bot_service.list_bots()
            await callback.answer("Bots ready")
            await _safe_edit_or_reply(
                callback,
                _bot_status_picker_text(records, 0),
                build_bot_status_keyboard(
                    [(item.id, item.bot_username, item.display_name, item.status) for item in records]
                ),
            )
            return

        if section == "Bots" and action == "Logs":
            records = await bot_service.list_bots()
            await callback.answer("Bot logs ready")
            await _safe_edit_or_reply(
                callback,
                _bot_logs_picker_text(records, 0),
                build_bot_logs_keyboard(
                    [(item.id, item.bot_username, item.display_name, item.status) for item in records]
                ),
            )
            return

        if section == "Bots" and action == "Settings":
            records = await bot_service.list_bots()
            await callback.answer("Bot settings ready")
            await _safe_edit_or_reply(
                callback,
                _bot_configs_picker_text(records, 0),
                build_bot_configs_keyboard(
                    [(item.id, item.bot_username, item.display_name, item.status) for item in records]
                ),
            )
            return

        if section == "Bots" and action == "Actions":
            await bot_service.set_pending_add(callback.from_user.id)
            await callback.answer("Send bot details")
            await _safe_edit_or_reply(
                callback,
                _bot_input_prompt(),
                build_section_actions_keyboard(section),
            )
            return

        if section == "Settings" and action == "Roles":
            if not is_owner(profile):
                await callback.answer("Only the owner can inspect role assignments.", show_alert=True)
                return

            users = await role_service.list_users_with_roles()
            if not users:
                await callback.answer("No assigned users yet.", show_alert=True)
                return

            lines = ["👤 Role assignments", ""]
            for summary in users[:20]:
                label = summary.display_name or summary.username or str(summary.telegram_user_id)
                roles = ", ".join(summary.role_keys) if summary.role_keys else "No roles"
                lines.append(f"- {label} ({summary.telegram_user_id}) -> {roles}")

            lines.append("")
            lines.append("Commands: /roles, /grant_role, /revoke_role, /user_roles, /my_roles")
            lines.append("Use these when you want finer role control.")
            await callback.answer("Roles ready")
            await _safe_edit_or_reply(
                callback,
                "\n".join(lines),
                build_section_actions_keyboard(section),
            )
            return

        if section == "Groups" and action == "View":
            records = await entity_service.list_groups()
            lines = [f"- {item.chat_identifier}" + (f" | {item.title}" if item.title else "") for item in records]
            await callback.answer("Groups ready")
            await _safe_edit_or_reply(
                callback,
                _entity_list_text(section, lines, 0),
                build_entity_list_keyboard(
                    section,
                    [(item.id, item.chat_identifier, item.title) for item in records],
                    0,
                ) if records else build_section_actions_keyboard(section),
            )
            return

        if section == "Groups" and action == "Pending":
            records = await entity_service.list_groups_by_status("PENDING")
            await callback.answer("Pending groups ready")
            await _safe_edit_or_reply(
                callback,
                _pending_entities_text(section, len(records)),
                build_pending_entities_keyboard(
                    section,
                    [(item.id, item.chat_identifier, item.title) for item in records],
                ) if records else build_section_actions_keyboard(section),
            )
            return

        if section == "Groups" and action == "Moderation":
            records = await entity_service.list_groups()
            await callback.answer("Moderation ready")
            await _safe_edit_or_reply(
                callback,
                _group_moderation_picker_text(records),
                build_group_moderation_keyboard(
                    [(item.id, item.chat_identifier, item.title) for item in records]
                ) if records else build_empty_recovery_keyboard("groups"),
            )
            return

        if section == "Groups" and action == "Warnings":
            records = await entity_service.list_groups()
            await callback.answer("Warnings ready")
            await _safe_edit_or_reply(
                callback,
                _group_warning_picker_text(records),
                build_group_warning_keyboard(
                    [(item.id, item.chat_identifier, item.title) for item in records]
                ) if records else build_empty_recovery_keyboard("groups"),
            )
            return

        if section == "Groups" and action == "Filters":
            records = await entity_service.list_groups()
            await callback.answer("Protection ready")
            await _safe_edit_or_reply(
                callback,
                _group_filter_picker_text(records),
                build_group_filter_keyboard(
                    [(item.id, item.chat_identifier, item.title) for item in records]
                ) if records else build_empty_recovery_keyboard("groups"),
            )
            return

        if section == "Groups" and action == "Welcome":
            records = await entity_service.list_groups()
            await callback.answer("Welcome settings ready")
            await _safe_edit_or_reply(
                callback,
                _group_welcome_picker_text(records),
                build_group_welcome_keyboard(
                    [(item.id, item.chat_identifier, item.title) for item in records]
                ) if records else build_empty_recovery_keyboard("groups"),
            )
            return

        await callback.answer(f"{section} -> {action}")
        await _safe_edit_or_reply(
            callback,
            f"{section}: {action}\n\nThis action is a placeholder for the next phase.",
            build_section_actions_keyboard(section),
        )

    @router.callback_query(F.data.startswith("post:channel:"))
    async def post_channel_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Post"):
            await callback.answer("You do not have access to posting.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Channels", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This channel is not active yet. Allow it first.", show_alert=True)
            return

        await target_preferences_service.record_recent(callback.from_user.id, record.id)
        await posting_service.set_pending_post(
            callback.from_user.id,
            record.chat_identifier,
            record.title,
        )
        await callback.answer("Send your message")
        await _safe_edit_or_reply(
            callback,
            _post_prompt(record.chat_identifier, record.title),
            build_section_actions_keyboard("Channels"),
        )

    @router.callback_query(F.data == "fbpromo:access")
    async def facebook_promo_access_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Facebook access ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_access_text(promo_profile, facebook_promo_service.mask_token),
            build_facebook_promo_access_v2_keyboard(bool(promo_profile.page_id), bool(promo_profile.page_access_token)),
        )

    @router.callback_query(F.data == "fbpromo:brief")
    async def facebook_promo_brief_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("AI brief ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_brief_text(promo_profile),
            build_facebook_promo_brief_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:accessdry")
    async def facebook_promo_access_dry_run_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        result = await facebook_promo_service.build_access_validation_dry_run(callback.from_user.id)
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Dry run ready" if result.ok else "Dry run blocked")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_access_dry_run_text(result),
            build_facebook_promo_access_v2_keyboard(
                bool(promo_profile.page_id),
                bool(promo_profile.page_access_token),
            ),
        )

    @router.callback_query(F.data == "fbpromo:accessvalidate")
    async def facebook_promo_access_validate_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        result = await facebook_promo_service.validate_page_access(callback.from_user.id)
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Validation complete" if result.ok else "Validation blocked")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_graph_response_text("Facebook access validation", result),
            build_facebook_promo_access_v2_keyboard(
                bool(promo_profile.page_id),
                bool(promo_profile.page_access_token),
            ),
        )

    @router.callback_query(F.data == "fbpromo:accesshelp")
    async def facebook_promo_access_help_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Access help ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_access_help_text(),
            build_facebook_promo_access_v2_keyboard(
                bool(promo_profile.page_id),
                bool(promo_profile.page_access_token),
            ),
        )

    @router.callback_query(F.data == "fbpromo:preferences")
    async def facebook_promo_preferences_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Style memory ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_preferences_text(promo_profile),
            build_facebook_promo_preferences_keyboard(),
        )

    @router.callback_query(F.data.startswith("fbpromo:pref:"))
    async def facebook_promo_preference_set_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        _, _, pref_key, pref_value = callback.data.split(":", maxsplit=3)
        promo_profile = await facebook_promo_service.set_preference(callback.from_user.id, pref_key, pref_value)
        await callback.answer("Style memory updated")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_preferences_text(promo_profile),
            build_facebook_promo_preferences_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:plan")
    async def facebook_promo_plan_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Working plan ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_working_plan_text(promo_profile),
            _facebook_promo_hub_keyboard(promo_profile),
        )

    @router.callback_query(F.data == "fbpromo:sample")
    async def facebook_promo_sample_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        await callback.answer("Sample ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_sample_text(),
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data == "fbpromo:guide")
    async def facebook_promo_guide_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Guide ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_guide_text(),
            _facebook_promo_hub_keyboard(promo_profile),
        )

    @router.callback_query(F.data == "fbpromo:campaigns")
    async def facebook_promo_campaigns_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        await callback.answer("Saved campaigns ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_campaigns_v2_text(campaigns),
            build_facebook_promo_campaigns_v2_keyboard(_facebook_promo_campaign_button_items(campaigns)),
        )

    @router.callback_query(F.data == "fbpromo:readyqueue")
    async def facebook_promo_ready_queue_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        all_campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        campaigns = [item for item in all_campaigns if item.status == "READY_TO_PUBLISH"]
        ready_items = FacebookPromoAIService.ready_campaign_index_items(all_campaigns)
        await callback.answer("Ready queue opened")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_ready_queue_text(campaigns),
            build_facebook_promo_ready_queue_keyboard(ready_items),
        )

    @router.callback_query(F.data == "fbpromo:published")
    async def facebook_promo_published_history_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        all_campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        campaigns = [item for item in all_campaigns if item.status == "PUBLISHED"]
        published_items = FacebookPromoAIService.published_campaign_index_items(all_campaigns)
        await callback.answer("Published history opened")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_published_history_text(campaigns),
            build_facebook_promo_published_history_keyboard(published_items),
        )

    @router.callback_query(F.data == "fbpromo:newtask")
    async def facebook_promo_new_task_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not FacebookPromoAIService.is_ready(promo_profile):
            if promo_profile.page_id and promo_profile.page_access_token and not (promo_profile.brand_notes or promo_profile.strategy_notes):
                await facebook_promo_service.set_pending_stage(callback.from_user.id, "await_strategy_brief")
                await callback.answer("Tell AI how to write first")
                await _safe_edit_or_reply(
                    callback,
                    _facebook_promo_missing_setup_text(promo_profile) + "\n\nSend your AI brief now.\n\nExample: Ami fashion page chalai, premium but friendly Bangla-English tone chai, offer thakle clear CTA dibe.",
                    build_facebook_promo_brief_keyboard(),
                )
                return

            await callback.answer("Finish setup first")
            await _safe_edit_or_reply(
                callback,
                _facebook_promo_missing_setup_text(promo_profile),
                _facebook_promo_hub_keyboard(promo_profile),
            )
            return

        await facebook_promo_service.start_new_task(callback.from_user.id)
        await callback.answer("Send the promo request")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_request_prompt() + "\n\nNeed to leave this flow? Send /cancel",
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data == "fbpromo:toggle")
    async def facebook_promo_toggle_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if promo_profile.status != "ACTIVE" and not FacebookPromoAIService.is_ready(promo_profile):
            await callback.answer("Finish Facebook access and AI brief first.", show_alert=True)
            return

        next_status = "INACTIVE" if promo_profile.status == "ACTIVE" else "ACTIVE"
        promo_profile = await facebook_promo_service.set_status(callback.from_user.id, next_status)
        await callback.answer(f"Facebook Promo AI: {promo_profile.status}")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_summary_text(promo_profile),
            _facebook_promo_hub_keyboard(promo_profile),
        )

    @router.callback_query(F.data == "fbpromo:clearaccess")
    async def facebook_promo_clear_access_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.clear_access(callback.from_user.id)
        await callback.answer("Saved access cleared")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_access_text(promo_profile, facebook_promo_service.mask_token),
            build_facebook_promo_access_v2_keyboard(False, False),
        )

    @router.callback_query(F.data.startswith("fbpromo:set:"))
    async def facebook_promo_set_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        _, _, field_name = callback.data.split(":", maxsplit=2)
        stage_map = {
            "page_id": "await_page_id",
            "token": "await_page_token",
            "brand": "await_brand_notes",
            "brief": "await_strategy_brief",
        }
        prompt_map = {
            "page_id": "Send the Facebook Page ID now.",
            "token": "Send the Facebook Page access token now.",
            "brand": "Tell me about the brand, niche, audience, and product line.",
            "brief": "Tell the AI how it should think before writing. Example: premium tone, less emoji, ask about offer and audience first.",
        }
        await facebook_promo_service.set_pending_stage(callback.from_user.id, stage_map[field_name])
        await callback.answer("Send the next detail")
        await _safe_edit_or_reply(
            callback,
            prompt_map[field_name] + "\n\nNeed to leave this flow? Send /cancel",
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data.startswith("fbpromo:goal:"))
    async def facebook_promo_goal_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending or pending.stage != "await_goal":
            await callback.answer("Start a new promo task first.", show_alert=True)
            return

        _, _, goal_key = callback.data.split(":", maxsplit=2)
        goal_label = FACEBOOK_PROMO_GOAL_LABELS.get(goal_key, goal_key.title())
        await facebook_promo_service.save_goal(callback.from_user.id, pending, goal_key, goal_label)
        refreshed = await facebook_promo_service.get_pending_action(callback.from_user.id)
        await callback.answer(f"Goal: {goal_label}")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_topic_prompt(refreshed),
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data.startswith("fbpromo:image:"))
    async def facebook_promo_image_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending or pending.stage != "await_image_mode":
            await callback.answer("Continue the promo task first.", show_alert=True)
            return

        _, _, image_mode = callback.data.split(":", maxsplit=2)
        await facebook_promo_service.save_image_mode(callback.from_user.id, pending, image_mode)
        refreshed = await facebook_promo_service.get_pending_action(callback.from_user.id)
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_recommendation_text(
                refreshed,
                facebook_promo_service.generate_recommendations(refreshed),
            ),
            build_facebook_promo_recommendation_keyboard(
                [(item.key, item.title) for item in facebook_promo_service.generate_recommendations(refreshed)]
            ),
        )

    @router.callback_query(F.data.startswith("fbpromo:angle:"))
    async def facebook_promo_angle_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending or pending.stage != "await_angle":
            await callback.answer("Continue the promo task first.", show_alert=True)
            return

        _, _, angle_key = callback.data.split(":", maxsplit=2)
        await facebook_promo_service.save_selected_angle(callback.from_user.id, pending, angle_key)
        refreshed = await facebook_promo_service.get_pending_action(callback.from_user.id)
        plan = facebook_promo_service.generate_strategy_plan(refreshed)
        await callback.answer("Plan ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_strategy_plan_text(refreshed, plan),
            build_facebook_promo_plan_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:plan:refine")
    async def facebook_promo_plan_refine_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending or pending.stage != "await_plan_review":
            await callback.answer("Open a strategy plan first.", show_alert=True)
            return
        await facebook_promo_service.save_pending_action(
            callback.from_user.id,
            type(pending)(
                stage="await_plan_feedback",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=pending.audience,
                image_mode=pending.image_mode,
                selected_angle=pending.selected_angle,
                plan_feedback=pending.plan_feedback,
            ),
        )
        await callback.answer("Send your refinement")
        await _safe_edit_or_reply(
            callback,
            "Tell me how you want this plan improved.\n\nExample: make it more premium, less emoji, stronger CTA, softer tone.\n\nNeed to leave this flow? Send /cancel",
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data == "fbpromo:plan:angles")
    async def facebook_promo_plan_angles_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending:
            await callback.answer("Start a promo task first.", show_alert=True)
            return
        await facebook_promo_service.save_pending_action(
            callback.from_user.id,
            type(pending)(
                stage="await_angle",
                user_request=pending.user_request,
                goal_key=pending.goal_key,
                goal_label=pending.goal_label,
                topic=pending.topic,
                audience=pending.audience,
                image_mode=pending.image_mode,
            ),
        )
        refreshed = await facebook_promo_service.get_pending_action(callback.from_user.id)
        recommendations = facebook_promo_service.generate_recommendations(refreshed)
        await callback.answer("Pick another angle")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_recommendation_text(refreshed, recommendations),
            build_facebook_promo_recommendation_keyboard([(item.key, item.title) for item in recommendations]),
        )

    @router.callback_query(F.data == "fbpromo:plan:save")
    async def facebook_promo_plan_save_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        pending = await facebook_promo_service.get_pending_action(callback.from_user.id)
        if not pending or pending.stage != "await_plan_review":
            await callback.answer("Open a strategy plan first.", show_alert=True)
            return
        profile_record = await facebook_promo_service.merge_task_into_strategy(callback.from_user.id, pending)
        await facebook_promo_service.clear_pending_action(callback.from_user.id)
        await callback.answer("Promo plan saved")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_task_summary_text(pending),
            _facebook_promo_hub_keyboard(profile_record),
        )

    @router.callback_query(F.data == "fbpromo:draft:generate")
    async def facebook_promo_generate_draft_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return

        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_plan_json:
            await callback.answer("Save a working plan first.", show_alert=True)
            return

        draft = await facebook_promo_service.generate_and_save_draft(callback.from_user.id)
        if not draft:
            await callback.answer("I could not build a draft from the saved plan.", show_alert=True)
            return

        await callback.answer("Draft ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_text(draft),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:draft:refine")
    async def facebook_promo_refine_draft_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_draft_json:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        await facebook_promo_service.set_pending_stage(callback.from_user.id, "await_draft_feedback")
        await callback.answer("Send draft feedback")
        await _safe_edit_or_reply(
            callback,
            "Tell me how to improve this draft.\n\nExamples:\n- make it shorter\n- make it more premium\n- less emoji\n- stronger CTA\n- softer tone\n\nNeed to leave this flow? Send /cancel",
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data == "fbpromo:draft:regenerate")
    async def facebook_promo_regenerate_draft_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_plan_json:
            await callback.answer("Save a working plan first.", show_alert=True)
            return
        draft = await facebook_promo_service.generate_and_save_draft(callback.from_user.id)
        if not draft:
            await callback.answer("I could not rebuild the draft.", show_alert=True)
            return
        await callback.answer("Draft regenerated")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_text(draft),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:draft:variants")
    async def facebook_promo_draft_variants_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        variants = await facebook_promo_service.get_saved_draft_variants(callback.from_user.id)
        if not variants:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        await callback.answer("Variant compare ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_variant_compare_text(variants),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:image:preview")
    async def facebook_promo_image_preview_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_draft_json:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        policy, image_prompt = await facebook_promo_service.build_image_generation_preview(
            callback.from_user.id,
            profile.role_keys,
        )
        await callback.answer("Image preview ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_image_preview_text(policy, image_prompt),
            build_facebook_promo_image_preview_keyboard(bool(image_prompt)),
        )

    @router.callback_query(F.data == "fbpromo:image:status")
    async def facebook_promo_image_status_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        policy = await facebook_promo_service.build_image_generation_policy(
            callback.from_user.id,
            profile.role_keys,
        )
        await callback.answer("Image safety status ready")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_image_safety_status_text(policy, facebook_promo_service),
            build_section_actions_keyboard("Automation"),
        )

    @router.callback_query(F.data == "fbpromo:image:confirm")
    async def facebook_promo_image_confirm_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        draft = facebook_promo_service.parse_draft(promo_profile.last_draft_json)
        if not draft:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        policy, _image_prompt = await facebook_promo_service.build_image_generation_preview(
            callback.from_user.id,
            profile.role_keys,
        )
        if policy.dry_run or not policy.allowed:
            await callback.answer("Image generation blocked safely", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                _facebook_promo_image_confirm_text(policy),
                build_facebook_promo_draft_v4_keyboard(),
            )
            return
        result = await facebook_promo_service.generate_campaign_image(callback.from_user.id, profile.role_keys)
        await callback.answer("Image generated" if result.ok else "Image generation blocked")
        if await _safe_send_generated_image(callback, result):
            return
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_image_result_text(result),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:draft:show")
    async def facebook_promo_show_current_draft_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        draft = facebook_promo_service.parse_draft(promo_profile.last_draft_json)
        if not draft:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        await callback.answer("Draft opened")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_v2_text(
                draft,
                facebook_promo_service.parse_generated_image(promo_profile.last_image_json),
            ),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data == "fbpromo:draft:savecampaign")
    async def facebook_promo_save_campaign_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        campaign = await facebook_promo_service.save_current_draft_as_campaign(callback.from_user.id)
        if not campaign:
            await callback.answer("Generate a draft first.", show_alert=True)
            return
        campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        await callback.answer("Campaign draft saved")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_campaigns_v2_text(campaigns),
            build_facebook_promo_campaigns_v2_keyboard(_facebook_promo_campaign_button_items(campaigns)),
        )

    @router.callback_query(F.data.startswith("fbpromo:campaign:"))
    async def facebook_promo_campaign_detail_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not open that saved draft.", show_alert=True)
            return
        if index < 0 or index >= len(campaigns):
            await callback.answer("That saved draft is no longer available.", show_alert=True)
            return
        campaign = campaigns[index]
        draft = facebook_promo_service.parse_draft(campaign.draft_json)
        if not draft:
            await callback.answer("I could not read that saved draft.", show_alert=True)
            return
        checklist = (
            await facebook_promo_service.build_campaign_publish_checklist(callback.from_user.id, index)
            if campaign.status == "READY_TO_PUBLISH"
            else None
        )
        await callback.answer("Saved draft opened")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_campaign_detail_v2_text(campaign, draft, checklist),
            _facebook_promo_campaign_keyboard_for(campaign, index),
        )

    @router.callback_query(F.data.startswith("fbpromo:campaignload:"))
    async def facebook_promo_campaign_load_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not load that draft.", show_alert=True)
            return
        draft = await facebook_promo_service.load_saved_campaign_as_current_draft(callback.from_user.id, index)
        if not draft:
            await callback.answer("That saved draft is no longer available.", show_alert=True)
            return
        await callback.answer("Draft loaded back")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_text(draft),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data.startswith("fbpromo:campaignapprove:"))
    async def facebook_promo_campaign_approve_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not approve that campaign.", show_alert=True)
            return
        campaign = await facebook_promo_service.mark_campaign_ready_to_publish(callback.from_user.id, index)
        if not campaign:
            await callback.answer("That saved campaign is no longer available.", show_alert=True)
            return
        campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        draft = facebook_promo_service.parse_draft(campaign.draft_json)
        checklist = await facebook_promo_service.build_campaign_publish_checklist(callback.from_user.id, index)
        await callback.answer("Marked ready to publish")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_campaign_detail_v2_text(campaign, draft, checklist),
            _facebook_promo_campaign_keyboard_for(campaign, index),
        )

    @router.callback_query(F.data.startswith("fbpromo:campaigndraft:"))
    async def facebook_promo_campaign_draft_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not update that campaign.", show_alert=True)
            return
        campaign = await facebook_promo_service.mark_campaign_draft(callback.from_user.id, index)
        if not campaign:
            await callback.answer("That saved campaign is no longer available.", show_alert=True)
            return
        draft = facebook_promo_service.parse_draft(campaign.draft_json)
        await callback.answer("Moved back to draft")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_campaign_detail_v2_text(campaign, draft),
            _facebook_promo_campaign_keyboard_for(campaign, index),
        )

    @router.callback_query(F.data.startswith("fbpromo:publishdry:"))
    async def facebook_promo_publish_dry_run_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not prepare that publish request.", show_alert=True)
            return
        result = await facebook_promo_service.build_campaign_publish_dry_run(callback.from_user.id, index)
        await callback.answer("Dry run ready" if result.ok else "Dry run blocked")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_publish_dry_run_text(result),
            build_facebook_promo_ready_campaign_detail_keyboard(index),
        )

    @router.callback_query(F.data.startswith("fbpromo:publishnow:"))
    async def facebook_promo_publish_now_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not publish that campaign.", show_alert=True)
            return
        result = await facebook_promo_service.build_campaign_publish_dry_run(callback.from_user.id, index)
        await callback.answer("Confirm before live publish" if result.ok else "Publish blocked")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_publish_confirm_text(result),
            build_facebook_promo_publish_confirm_keyboard(index)
            if result.ok
            else build_facebook_promo_ready_campaign_detail_keyboard(index),
        )

    @router.callback_query(F.data.startswith("fbpromo:publishconfirm:"))
    async def facebook_promo_publish_confirm_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        _, _, index_raw = callback.data.split(":", maxsplit=2)
        try:
            index = int(index_raw)
        except ValueError:
            await callback.answer("I could not publish that campaign.", show_alert=True)
            return
        result = await facebook_promo_service.publish_campaign(callback.from_user.id, index)
        campaigns = await facebook_promo_service.list_saved_campaigns(callback.from_user.id)
        campaign = campaigns[index] if 0 <= index < len(campaigns) else None
        await callback.answer("Publish complete" if result.ok else "Publish blocked")
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_graph_response_text("Facebook publish", result),
            _facebook_promo_campaign_keyboard_for(campaign, index)
            if campaign
            else build_facebook_promo_ready_campaign_detail_keyboard(index),
        )

    @router.callback_query(F.data.startswith("fbpromo:draft:preset:"))
    async def facebook_promo_draft_preset_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_draft_json:
            await callback.answer("Generate a draft first.", show_alert=True)
            return

        _, _, _, preset_key = callback.data.split(":", maxsplit=3)
        instruction_map = {
            "premium": "make it more premium",
            "shorter": "make it shorter",
            "urgent": "make it more urgent with stronger CTA",
        }
        instruction = instruction_map.get(preset_key)
        if not instruction:
            await callback.answer("Unknown preset.", show_alert=True)
            return

        draft = await facebook_promo_service.refine_saved_draft(callback.from_user.id, instruction)
        if not draft:
            await callback.answer("I could not update the draft.", show_alert=True)
            return

        label_map = {
            "premium": "Premium version ready",
            "shorter": "Shorter version ready",
            "urgent": "Urgent version ready",
        }
        await callback.answer(label_map.get(preset_key, "Draft updated"))
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_text(draft),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data.startswith("fbpromo:image:preset:"))
    async def facebook_promo_image_preset_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("This action is not available for your role right now.", show_alert=True)
            return
        promo_profile = await facebook_promo_service.get_profile(callback.from_user.id)
        if not promo_profile.last_draft_json:
            await callback.answer("Generate a draft first.", show_alert=True)
            return

        _, _, _, preset_key = callback.data.split(":", maxsplit=3)
        instruction_map = {
            "minimal": "make the image concept minimal",
            "lifestyle": "make the image concept lifestyle",
            "sale": "make the image concept sale-focused",
        }
        instruction = instruction_map.get(preset_key)
        if not instruction:
            await callback.answer("Unknown image preset.", show_alert=True)
            return

        draft = await facebook_promo_service.refine_saved_image_concept(callback.from_user.id, instruction)
        if not draft:
            await callback.answer("I could not update the image concept.", show_alert=True)
            return

        label_map = {
            "minimal": "Minimal image concept ready",
            "lifestyle": "Lifestyle image concept ready",
            "sale": "Sale visual concept ready",
        }
        await callback.answer(label_map.get(preset_key, "Image concept updated"))
        await _safe_edit_or_reply(
            callback,
            _facebook_promo_draft_text(draft),
            build_facebook_promo_draft_v4_keyboard(),
        )

    @router.callback_query(F.data.startswith("automation:create:"))
    async def automation_create_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, template_key = callback.data.split(":", maxsplit=2)
        record = await automation_service.create_rule(template_key, profile.user.id)
        if not record:
            await callback.answer("Automation storage is not available", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="CREATE_AUTOMATION_RULE",
            target_type="AUTOMATION",
            target_id=record.template_key,
            details=record.schedule_key,
        )
        await callback.answer("Automation saved")
        await _safe_edit_or_reply(
            callback,
            _automation_rule_detail_text(record),
            build_automation_rule_detail_keyboard(record.id, record.status == "ACTIVE"),
        )

    @router.callback_query(F.data.startswith("automation:detail:"))
    async def automation_detail_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, rule_id_raw = callback.data.split(":", maxsplit=2)
        record = await automation_service.get_rule(int(rule_id_raw))
        if not record:
            await callback.answer("Automation rule not found", show_alert=True)
            return

            await callback.answer("Rule ready")
        await _safe_edit_or_reply(
            callback,
            _automation_rule_detail_text(record),
            build_automation_rule_detail_keyboard(record.id, record.status == "ACTIVE"),
        )

    @router.callback_query(F.data.startswith("automation:toggle:"))
    async def automation_toggle_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, rule_id_raw = callback.data.split(":", maxsplit=2)
        record = await automation_service.toggle_rule(int(rule_id_raw))
        if not record:
            await callback.answer("Automation rule not found", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TOGGLE_AUTOMATION_RULE",
            target_type="AUTOMATION",
            target_id=record.template_key,
            details=record.status,
        )
        await callback.answer(f"Rule: {record.status}")
        await _safe_edit_or_reply(
            callback,
            _automation_rule_detail_text(record),
            build_automation_rule_detail_keyboard(record.id, record.status == "ACTIVE"),
        )

    @router.callback_query(F.data.startswith("automation:delete:"))
    async def automation_delete_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, rule_id_raw = callback.data.split(":", maxsplit=2)
        record = await automation_service.get_rule(int(rule_id_raw))
        if not record:
            await callback.answer("Automation rule not found", show_alert=True)
            return

        deleted = await automation_service.delete_rule(record.id)
        if not deleted:
            await callback.answer("Delete failed", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="DELETE_AUTOMATION_RULE",
            target_type="AUTOMATION",
            target_id=record.template_key,
        )
        refreshed = await automation_service.list_rules()
        await callback.answer("Automation deleted")
        await _safe_edit_or_reply(
            callback,
            _automation_rules_text(refreshed),
            build_automation_rules_keyboard(
                [(item.id, item.template_name, item.status) for item in refreshed]
            ),
        )

    @router.callback_query(F.data.startswith("bot:detail:"))
    async def bot_detail_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, bot_id_raw = callback.data.split(":", maxsplit=2)
        record = await bot_service.get_bot(int(bot_id_raw))
        if not record:
            await callback.answer("I could not find that bot.", show_alert=True)
            return

            await callback.answer("Bot details ready")
        await _safe_edit_or_reply(
            callback,
            _bot_detail_text(record),
            build_bot_detail_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("bot:refresh:"))
    async def bot_refresh_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, bot_id_raw = callback.data.split(":", maxsplit=2)
        record = await bot_service.refresh_status(int(bot_id_raw))
        if not record:
            await callback.answer("I could not find that bot.", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="REFRESH_MANAGED_BOT_STATUS",
            target_type="BOT",
            target_id=record.bot_username,
            details=record.status,
        )
        await callback.answer(f"Status: {record.status}")
        await _safe_edit_or_reply(
            callback,
            _bot_detail_text(record),
            build_bot_detail_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("bot:action:"))
    async def bot_action_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, bot_id_raw = callback.data.split(":", maxsplit=2)
        record, result = await bot_service.trigger_action(int(bot_id_raw))
        if not record:
            await callback.answer(result, show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TRIGGER_MANAGED_BOT_ACTION",
            target_type="BOT",
            target_id=record.bot_username,
            details=result,
        )
        await callback.answer(result[:60], show_alert=True)
        await _safe_edit_or_reply(
            callback,
            _bot_detail_text(record) + f"\n\nLast action result: {result}",
            build_bot_detail_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("bot:logs:"))
    async def bot_logs_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, bot_id_raw = callback.data.split(":", maxsplit=2)
        record = await bot_service.get_bot(int(bot_id_raw))
        if not record:
            await callback.answer("I could not find that bot.", show_alert=True)
            return

        rows = []
        if app_context.oracle_client:
            rows = await asyncio.to_thread(
                AuditRepository(app_context.oracle_client).list_recent_for_target,
                "BOT",
                record.bot_username,
                10,
            )
            await callback.answer("Bot logs ready")
        await _safe_edit_or_reply(
            callback,
            _bot_logs_text(record, rows),
            build_bot_detail_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("bot:config:"))
    async def bot_config_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, bot_id_raw = callback.data.split(":", maxsplit=2)
        record = await bot_service.get_bot(int(bot_id_raw))
        if not record:
            await callback.answer("I could not find that bot.", show_alert=True)
            return

            await callback.answer("Bot settings ready")
        await _safe_edit_or_reply(
            callback,
            _bot_config_text(record),
            build_bot_detail_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("broadcast:toggle:"))
    async def broadcast_toggle_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Broadcast", "Select"):
            await callback.answer("You do not have access to broadcast selection.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        selection = await posting_service.toggle_broadcast_target(callback.from_user.id, int(entity_id_raw))
        records = await entity_service.list_channels()
        ranked_items = await ranked_channel_items(callback.from_user.id)
        quick_items = await quick_channel_items(callback.from_user.id)
        await callback.answer("Updated")
        await _safe_edit_or_reply(
            callback,
            _broadcast_select_text(len(records), len(selection.selected_ids)),
            build_broadcast_select_keyboard(
                quick_items + ranked_items,
                set(selection.selected_ids),
            ),
        )

    @router.callback_query(F.data.startswith("favorite:"))
    async def favorite_target_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, context, entity_id_raw = callback.data.split(":", maxsplit=2)
        entity_id = int(entity_id_raw)
        record = await entity_service.get_entity("Channels", entity_id)
        if not record or not record.is_active:
            await callback.answer("Only active channels can be favorited.", show_alert=True)
            return

        favorite_ids = await target_preferences_service.toggle_favorite(callback.from_user.id, entity_id)
        ranked_items = await ranked_channel_items(callback.from_user.id)
        quick_items = await quick_channel_items(callback.from_user.id)
        favorite_on = entity_id in favorite_ids

        if context == "post":
            await callback.answer("Saved to favorites" if favorite_on else "Removed from favorites")
            await _safe_edit_or_reply(
                callback,
                _channel_picker_text("post", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in ranked_items]),
                build_channel_post_keyboard(quick_items + ranked_items, "all"),
            )
            return

        if context == "schedule":
            await callback.answer("Saved to favorites" if favorite_on else "Removed from favorites")
            await _safe_edit_or_reply(
                callback,
                _channel_picker_text("schedule", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in ranked_items])
                + "\n\nUse /schedule_list to review saved schedules.",
                build_channel_schedule_keyboard(quick_items + ranked_items, "all"),
            )
            return

        if context == "broadcast":
            selection = await posting_service.get_broadcast_selection(callback.from_user.id)
            all_records = await entity_service.list_channels()
            await callback.answer("Saved to favorites" if favorite_on else "Removed from favorites")
            await _safe_edit_or_reply(
                callback,
                _broadcast_select_text(len(all_records), len(selection.selected_ids)),
                build_broadcast_select_keyboard(quick_items + ranked_items, set(selection.selected_ids), "all"),
            )
            return

        await callback.answer("Updated", show_alert=False)

    @router.callback_query(F.data.startswith("picker:"))
    async def picker_filter_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, context, filter_mode = callback.data.split(":", maxsplit=2)
        ranked_items = await ranked_channel_items(callback.from_user.id)
        quick_items = await quick_channel_items(callback.from_user.id)
        filtered_items = _filter_ranked_channel_items(ranked_items, filter_mode)

        if context == "post":
            await callback.answer("Showing favorites" if filter_mode == "favorites" else "Showing all")
            await _safe_edit_or_reply(
                callback,
                _channel_picker_text("post", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in filtered_items]),
                build_channel_post_keyboard(quick_items + filtered_items, filter_mode),
            )
            return

        if context == "schedule":
            await callback.answer("Showing favorites" if filter_mode == "favorites" else "Showing all")
            await _safe_edit_or_reply(
                callback,
                _channel_picker_text("schedule", [(None, is_favorite, is_recent) for _, _, _, is_favorite, is_recent in filtered_items])
                + "\n\nUse /schedule_list to review saved schedules.",
                build_channel_schedule_keyboard(quick_items + filtered_items, filter_mode),
            )
            return

        if context == "broadcast":
            selection = await posting_service.get_broadcast_selection(callback.from_user.id)
            all_records = await entity_service.list_channels()
            await callback.answer("Showing favorites" if filter_mode == "favorites" else "Showing all")
            await _safe_edit_or_reply(
                callback,
                _broadcast_select_text(len(all_records), len(selection.selected_ids)),
                build_broadcast_select_keyboard(quick_items + filtered_items, set(selection.selected_ids), filter_mode),
            )
            return

        await callback.answer("Updated")

    @router.callback_query(F.data.startswith("pickersearch:"))
    async def picker_search_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, context = callback.data.split(":", maxsplit=1)
        await target_preferences_service.set_search_context(callback.from_user.id, context)
        await callback.answer("Send a title, username, or keyword")
        await callback.message.answer(_picker_search_prompt(context))

    @router.callback_query(F.data.startswith("group:moderation:"))
    async def group_moderation_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Moderation"):
            await callback.answer("You do not have access to group moderation.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        verified, details = await _get_group_moderation_state(callback.bot, record.chat_identifier)
        if not verified:
            await callback.answer("Verification failed", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                f"Group moderation\n\n{details}",
                build_group_control_keyboard(record.id),
            )
            return

        await callback.answer("Group controls ready")
        await _safe_edit_or_reply(
            callback,
            details,
            build_group_control_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("group:warnings:"))
    async def group_warnings_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Warnings"):
            await callback.answer("You do not have access to group warnings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        entries = await warning_service.get_top_warnings(_warning_group_key(record))
        await callback.answer("Warnings loaded")
        await _safe_edit_or_reply(
            callback,
            _warning_panel_text(record.title or record.chat_identifier, entries),
            build_group_warning_control_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("groupwarn:reset:"))
    async def group_warning_reset_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Warnings"):
            await callback.answer("You do not have access to group warnings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        await warning_service.clear_group_warnings(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="RESET_GROUP_WARNINGS",
            target_type="GROUP",
            target_id=record.chat_identifier,
        )
        await callback.answer("Warnings reset")
        await _safe_edit_or_reply(
            callback,
            _warning_panel_text(record.title or record.chat_identifier, []),
            build_group_warning_control_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("group:filters:"))
    async def group_filters_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Filters"):
            await callback.answer("You do not have access to group filters.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await filter_service.get_state(_warning_group_key(record))
        await callback.answer("Filters loaded")
        await _safe_edit_or_reply(
            callback,
            _filter_panel_text(record.title or record.chat_identifier, state),
            build_group_filter_control_keyboard(record.id, state.anti_link_enabled, state.bad_word_enabled),
        )

    @router.callback_query(F.data.startswith("groupfilter:antilink:"))
    async def group_filter_antilink_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Filters"):
            await callback.answer("You do not have access to group filters.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await filter_service.toggle_anti_link(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TOGGLE_ANTI_LINK_FILTER",
            target_type="GROUP",
            target_id=record.chat_identifier,
            details=f"enabled={state.anti_link_enabled}",
        )
        await callback.answer("Anti-link updated")
        await _safe_edit_or_reply(
            callback,
            _filter_panel_text(record.title or record.chat_identifier, state),
            build_group_filter_control_keyboard(record.id, state.anti_link_enabled, state.bad_word_enabled),
        )

    @router.callback_query(F.data.startswith("groupfilter:badword:"))
    async def group_filter_badword_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Filters"):
            await callback.answer("You do not have access to group filters.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await filter_service.toggle_bad_word(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TOGGLE_BAD_WORD_FILTER",
            target_type="GROUP",
            target_id=record.chat_identifier,
            details=f"enabled={state.bad_word_enabled}",
        )
        await callback.answer("Bad-word filter updated")
        await _safe_edit_or_reply(
            callback,
            _filter_panel_text(record.title or record.chat_identifier, state),
            build_group_filter_control_keyboard(record.id, state.anti_link_enabled, state.bad_word_enabled),
        )

    @router.callback_query(F.data.startswith("groupfilter:clearbad:"))
    async def group_filter_clear_bad_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Filters"):
            await callback.answer("You do not have access to group filters.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await filter_service.clear_custom_bad_words(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="CLEAR_GROUP_CUSTOM_BAD_WORDS",
            target_type="GROUP",
            target_id=record.chat_identifier,
        )
        await callback.answer("Custom list cleared")
        await _safe_edit_or_reply(
            callback,
            _filter_panel_text(record.title or record.chat_identifier, state),
            build_group_filter_control_keyboard(record.id, state.anti_link_enabled, state.bad_word_enabled),
        )

    @router.callback_query(F.data.startswith("group:welcome:"))
    async def group_welcome_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Welcome"):
            await callback.answer("You do not have access to welcome settings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await group_event_service.get_state(_warning_group_key(record))
        await callback.answer("Welcome settings loaded")
        await _safe_edit_or_reply(
            callback,
            _welcome_panel_text(record.title or record.chat_identifier, state),
            build_group_welcome_control_keyboard(record.id, state.welcome_enabled, state.join_log_enabled),
        )

    @router.callback_query(F.data.startswith("groupwelcome:toggle:"))
    async def group_welcome_toggle_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Welcome"):
            await callback.answer("You do not have access to welcome settings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        state = await group_event_service.toggle_welcome(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TOGGLE_GROUP_WELCOME",
            target_type="GROUP",
            target_id=record.chat_identifier,
            details=f"enabled={state.welcome_enabled}",
        )
        await callback.answer("Welcome setting updated")
        await _safe_edit_or_reply(
            callback,
            _welcome_panel_text(record.title or record.chat_identifier, state),
            build_group_welcome_control_keyboard(record.id, state.welcome_enabled, state.join_log_enabled),
        )

    @router.callback_query(F.data.startswith("groupwelcome:logs:"))
    async def group_welcome_logs_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Welcome"):
            await callback.answer("You do not have access to welcome settings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("Only active groups are available.", show_alert=True)
            return

        state = await group_event_service.toggle_join_log(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="TOGGLE_GROUP_JOIN_LOG",
            target_type="GROUP",
            target_id=record.chat_identifier,
            details=f"enabled={state.join_log_enabled}",
        )
        await callback.answer("Join log updated")
        await _safe_edit_or_reply(
            callback,
            _welcome_panel_text(record.title or record.chat_identifier, state),
            build_group_welcome_control_keyboard(record.id, state.welcome_enabled, state.join_log_enabled),
        )

    @router.callback_query(F.data.startswith("groupwelcome:clear:"))
    async def group_welcome_clear_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Welcome"):
            await callback.answer("You do not have access to welcome settings.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("Only active groups are available.", show_alert=True)
            return

        state = await group_event_service.clear_welcome_template(_warning_group_key(record))
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="CLEAR_GROUP_WELCOME_TEMPLATE",
            target_type="GROUP",
            target_id=record.chat_identifier,
        )
        await callback.answer("Welcome template cleared")
        await _safe_edit_or_reply(
            callback,
            _welcome_panel_text(record.title or record.chat_identifier, state),
            build_group_welcome_control_keyboard(record.id, state.welcome_enabled, state.join_log_enabled),
        )

    @router.callback_query(F.data.startswith("group:lock:"))
    async def group_lock_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        verified, details = await _get_group_moderation_state(callback.bot, record.chat_identifier)
        if not verified:
            await callback.answer("Cannot lock", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                f"Group moderation\n\n{details}",
                build_group_control_keyboard(record.id),
            )
            return

        try:
            await callback.bot.set_chat_permissions(record.chat_identifier, permissions=_locked_permissions())
        except TelegramBadRequest as exc:
            await callback.answer("Lock failed", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                f"{details}\n\nLock failed: {exc.message}",
                build_group_control_keyboard(record.id),
            )
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="LOCK_GROUP",
            target_type="GROUP",
            target_id=record.chat_identifier,
        )
        _, refreshed = await _get_group_moderation_state(callback.bot, record.chat_identifier)
        await callback.answer("Group locked")
        await _safe_edit_or_reply(
            callback,
            f"{refreshed}\n\nMembers are now muted at the group level.",
            build_group_control_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("group:unlock:"))
    async def group_unlock_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Groups", "Moderation"):
            await callback.answer("You do not have access to group moderation.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Groups", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This group is not active yet. Allow it first.", show_alert=True)
            return

        verified, details = await _get_group_moderation_state(callback.bot, record.chat_identifier)
        if not verified:
            await callback.answer("Cannot unlock", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                f"Group moderation\n\n{details}",
                build_group_control_keyboard(record.id),
            )
            return

        try:
            await callback.bot.set_chat_permissions(record.chat_identifier, permissions=_unlock_permissions())
        except TelegramBadRequest as exc:
            await callback.answer("Unlock failed", show_alert=True)
            await _safe_edit_or_reply(
                callback,
                f"{details}\n\nUnlock failed: {exc.message}",
                build_group_control_keyboard(record.id),
            )
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="UNLOCK_GROUP",
            target_type="GROUP",
            target_id=record.chat_identifier,
        )
        _, refreshed = await _get_group_moderation_state(callback.bot, record.chat_identifier)
        await callback.answer("Group unlocked")
        await _safe_edit_or_reply(
            callback,
            f"{refreshed}\n\nMembers can send messages again.",
            build_group_control_keyboard(record.id),
        )

    @router.callback_query(F.data == "broadcast:clear")
    async def broadcast_clear_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Broadcast", "Select"):
            await callback.answer("You do not have access to broadcast selection.", show_alert=True)
            return

        await posting_service.clear_broadcast_selection(callback.from_user.id)
        records = await entity_service.list_channels()
        ranked_items = await ranked_channel_items(callback.from_user.id)
        await callback.answer("Selection cleared")
        await _safe_edit_or_reply(
            callback,
            _broadcast_select_text(len(records), 0),
            build_broadcast_select_keyboard(
                ranked_items,
                set(),
                "all",
            ),
        )

    @router.callback_query(F.data == "broadcast:compose")
    async def broadcast_compose_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Broadcast", "Select"):
            await callback.answer("You do not have access to broadcast selection.", show_alert=True)
            return

        selection = await posting_service.get_broadcast_selection(callback.from_user.id)
        if not selection.selected_ids:
            await callback.answer("Select at least one channel", show_alert=True)
            return

        records = await entity_service.list_channels()
        selected_records = [item for item in records if item.id in set(selection.selected_ids)]
        if not selected_records:
            await callback.answer("No valid active targets selected.", show_alert=True)
            return

        for item in selected_records[:6]:
            await target_preferences_service.record_recent(callback.from_user.id, item.id)
        await posting_service.set_pending_broadcast(
            callback.from_user.id,
            [
                {
                    "channel_identifier": item.chat_identifier,
                    "channel_title": item.title,
                }
                for item in selected_records
            ],
        )
        await callback.answer("Send broadcast text")
        await _safe_edit_or_reply(
            callback,
            _broadcast_prompt(len(selected_records)),
            build_section_actions_keyboard("Broadcast"),
        )

    @router.callback_query(F.data.startswith("schedule:channel:"))
    async def schedule_channel_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, _, entity_id_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Channels", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This channel is not active yet. Allow it first.", show_alert=True)
            return

        await target_preferences_service.record_recent(callback.from_user.id, record.id)
        await schedule_service.start_schedule(
            callback.from_user.id,
            record.chat_identifier,
            record.title,
        )
        await callback.answer("Choose schedule type")
        await _safe_edit_or_reply(
            callback,
            _schedule_mode_text(record.chat_identifier, record.title),
            build_schedule_mode_keyboard(record.id),
        )

    @router.callback_query(F.data.startswith("schedulemode:"))
    async def schedule_mode_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, entity_id_raw, schedule_mode = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Channels", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This channel is not active yet. Allow it first.", show_alert=True)
            return

        pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending:
            await schedule_service.start_schedule(
                callback.from_user.id,
                record.chat_identifier,
                record.title,
            )
            pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending:
            await callback.answer("Could not start scheduling", show_alert=True)
            return

        await schedule_service.set_schedule_mode(callback.from_user.id, pending, schedule_mode)
        if schedule_mode == "WEEKLY":
            await callback.answer("Choose weekday")
            await _safe_edit_or_reply(
                callback,
                "📆 Weekly schedule\n\nChoose the weekday first.",
                build_schedule_weekday_keyboard(record.id),
            )
            return
        if schedule_mode == "MONTHLY":
            await callback.answer("Choose monthly date")
            await _safe_edit_or_reply(
                callback,
                "🗓️ Monthly schedule\n\nChoose the monthly date first.",
                build_schedule_monthday_keyboard(record.id),
            )
            return
        await callback.answer("Send schedule time")
        await _safe_edit_or_reply(
            callback,
            _schedule_time_prompt_for_mode(record.chat_identifier, record.title, schedule_mode),
            build_schedule_time_shortcuts_keyboard(_schedule_shortcut_options(schedule_mode)),
        )

    @router.callback_query(F.data.startswith("scheduleweekday:"))
    async def schedule_weekday_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, entity_id_raw, weekday_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Channels", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("This channel is not active yet. Allow it first.", show_alert=True)
            return

        pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending:
            await callback.answer("No open schedule draft right now.", show_alert=True)
            return

        await schedule_service.set_weekday(callback.from_user.id, pending, int(weekday_raw))
        refreshed = await schedule_service.get_pending(callback.from_user.id)
        await callback.answer("Choose time")
        await _safe_edit_or_reply(
            callback,
            _schedule_time_prompt_for_mode(record.chat_identifier, record.title, "WEEKLY"),
            build_schedule_time_shortcuts_keyboard(_schedule_shortcut_options("WEEKLY")),
        )

    @router.callback_query(F.data.startswith("schedulemonthday:"))
    async def schedule_monthday_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, entity_id_raw, monthday_raw = callback.data.split(":", maxsplit=2)
        record = await entity_service.get_entity("Channels", int(entity_id_raw))
        if not record or not record.is_active:
            await callback.answer("Only active channels can be scheduled.", show_alert=True)
            return

        pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending:
            await callback.answer("No open schedule draft right now.", show_alert=True)
            return

        await schedule_service.set_monthday(callback.from_user.id, pending, int(monthday_raw))
        refreshed = await schedule_service.get_pending(callback.from_user.id)
        await callback.answer("Choose time")
        await _safe_edit_or_reply(
            callback,
            _schedule_time_prompt_for_mode(record.chat_identifier, record.title, "MONTHLY"),
            build_schedule_time_shortcuts_keyboard(_schedule_shortcut_options("MONTHLY")),
        )

    @router.callback_query(F.data.startswith("schedulequick:"))
    async def schedule_quick_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending or pending.stage != "await_time":
            await callback.answer("No open schedule draft right now.", show_alert=True)
            return

        _, token = callback.data.split(":", maxsplit=1)
        raw_value = _resolve_schedule_shortcut_value(pending, token)
        if not raw_value:
            await callback.answer("Shortcut not available", show_alert=True)
            return

        try:
            parsed_schedule = _resolve_schedule_spec_for_pending(
                pending,
                raw_value,
                schedule_service.parse_schedule_time,
            )
        except ValueError:
            await callback.answer("Shortcut failed", show_alert=True)
            return

        normalized_schedule = parsed_schedule.scheduled_for.strftime("%Y-%m-%d %H:%M")
        await schedule_service.advance_to_message(
            callback.from_user.id,
            pending,
            normalized_schedule,
            parsed_schedule.recurrence_key,
        )
        await callback.answer("Shortcut applied")
        await _safe_edit_or_reply(
            callback,
            _schedule_message_prompt(
                pending.channel_identifier,
                pending.channel_title,
                normalized_schedule,
            ),
            build_section_actions_keyboard("Channels"),
        )

    @router.callback_query(F.data.startswith("scheduleconfirm:"))
    async def schedule_confirm_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, action = callback.data.split(":", maxsplit=1)
        pending = await schedule_service.get_pending(callback.from_user.id)
        if not pending or pending.stage != "await_confirm":
            await callback.answer("No open schedule draft right now.", show_alert=True)
            return

        if action == "time":
            await schedule_service.return_to_time_step(callback.from_user.id, pending)
            await callback.answer("Edit the schedule time")
            refreshed = await schedule_service.get_pending(callback.from_user.id)
            await _safe_edit_or_reply(
                callback,
                _schedule_time_prompt_for_mode(
                    refreshed.channel_identifier,
                    refreshed.channel_title,
                    refreshed.schedule_mode,
                ),
                build_schedule_time_shortcuts_keyboard(
                    _schedule_shortcut_options(refreshed.schedule_mode)
                ),
            )
            return

        if action == "cancel":
            await schedule_service.clear_pending(callback.from_user.id)
            await callback.answer("Schedule draft cleared")
            await _safe_edit_or_reply(
                callback,
                "❌ Schedule draft canceled.\n\nYou can start a new one anytime from ⏰ Schedule.",
                build_section_actions_keyboard("Channels"),
            )
            return

        record = await schedule_service.create_scheduled_post(
            pending,
            pending.draft_message_text or "",
            profile.user.id,
            media_path=pending.draft_media_path,
            media_name=pending.draft_media_name,
            media_type=pending.draft_media_type,
        )
        await schedule_service.clear_pending(callback.from_user.id)
        if not record:
            await callback.answer("Could not save the scheduled post.", show_alert=True)
            return

        details = f"{record.scheduled_for}"
        if record.media_path:
            details += "|media=1"
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="CREATE_SCHEDULED_POST",
            target_type="CHANNEL",
            target_id=record.channel_identifier,
            details=details,
        )
        await callback.answer("Schedule saved")
        await _safe_edit_or_reply(
            callback,
            f"✅ Scheduled for {record.channel_title or record.channel_identifier} at {record.scheduled_for}.",
            None,
        )
        await callback.message.answer(
            "You can review schedules anytime with /schedule_list.",
            reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(callback.from_user.id)),
        )
        await callback.message.answer(
            "What would you like to do next?",
            reply_markup=build_success_next_keyboard("schedule_saved"),
        )

    @router.message(Command("schedule_list"))
    async def schedule_list_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer("You do not have access to this action.")
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await message.answer("You do not have access to scheduling.")
            return

        records = await schedule_service.list_manageable()
        labels = [
            (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
            for item in records
        ]
        await message.answer(
            _schedule_list_text(records),
            reply_markup=build_schedule_list_keyboard(labels),
        )

    @router.callback_query(F.data.startswith("schedule:cancel:"))
    async def schedule_cancel_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, _, schedule_id_raw = callback.data.split(":", maxsplit=2)
        record = await schedule_service.get_by_id(int(schedule_id_raw))
        if not record:
            await callback.answer("Schedule not found", show_alert=True)
            return

        await schedule_service.update_status(record.id, "CANCELED")
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="CANCEL_SCHEDULED_POST",
            target_type="CHANNEL",
            target_id=record.channel_identifier,
            details=f"schedule_id={record.id}",
        )
        await callback.answer("Schedule draft cleared")
        updated = await schedule_service.list_manageable()
        labels = [
            (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
            for item in updated
        ]
        await _safe_edit_or_reply(
            callback,
            _schedule_list_text(updated),
            build_schedule_list_keyboard(labels),
        )

    @router.callback_query(F.data.startswith("schedule:pause:"))
    async def schedule_pause_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, _, schedule_id_raw = callback.data.split(":", maxsplit=2)
        record = await schedule_service.get_by_id(int(schedule_id_raw))
        if not record or not record.recurrence_key:
            await callback.answer("Recurring schedule not found", show_alert=True)
            return

        await schedule_service.update_status(record.id, "PAUSED")
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="PAUSE_RECURRING_SCHEDULE",
            target_type="CHANNEL",
            target_id=record.channel_identifier,
            details=f"schedule_id={record.id}",
        )
        await callback.answer("Recurring schedule paused")
        updated = await schedule_service.list_manageable()
        labels = [
            (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
            for item in updated
        ]
        await _safe_edit_or_reply(callback, _schedule_list_text(updated), build_schedule_list_keyboard(labels))

    @router.callback_query(F.data.startswith("schedule:resume:"))
    async def schedule_resume_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, _, schedule_id_raw = callback.data.split(":", maxsplit=2)
        record = await schedule_service.get_by_id(int(schedule_id_raw))
        if not record or not record.recurrence_key:
            await callback.answer("Recurring schedule not found", show_alert=True)
            return

        await schedule_service.update_status(record.id, "PENDING")
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="RESUME_RECURRING_SCHEDULE",
            target_type="CHANNEL",
            target_id=record.channel_identifier,
            details=f"schedule_id={record.id}",
        )
        await callback.answer("Recurring schedule resumed")
        updated = await schedule_service.list_manageable()
        labels = [
            (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
            for item in updated
        ]
        await _safe_edit_or_reply(callback, _schedule_list_text(updated), build_schedule_list_keyboard(labels))

    @router.callback_query(F.data.startswith("schedule:skip:"))
    async def schedule_skip_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        if not can_run_section_action(profile, "Channels", "Schedule"):
            await callback.answer("You do not have access to scheduling.", show_alert=True)
            return

        _, _, schedule_id_raw = callback.data.split(":", maxsplit=2)
        updated_record = await schedule_service.skip_next(int(schedule_id_raw))
        if not updated_record:
            await callback.answer("Could not skip next run", show_alert=True)
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="SKIP_NEXT_RECURRING_SCHEDULE",
            target_type="CHANNEL",
            target_id=updated_record.channel_identifier,
            details=f"schedule_id={updated_record.id}|next={updated_record.scheduled_for}",
        )
        await callback.answer("Next occurrence skipped")
        updated = await schedule_service.list_manageable()
        labels = [
            (item.id, item.channel_title or item.channel_identifier, item.recurrence_key, item.status)
            for item in updated
        ]
        await _safe_edit_or_reply(callback, _schedule_list_text(updated), build_schedule_list_keyboard(labels))

    @router.callback_query(F.data.startswith("entity:"))
    async def entity_review_callback(callback: CallbackQuery) -> None:
        await callback.answer("Processing...")
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.message.answer("You do not have access to this action.")
            return

        _, section, entity_id_raw, status = callback.data.split(":", maxsplit=3)
        if not can_run_section_action(profile, section, "Pending"):
            await callback.message.answer("You do not have access to entity review.")
            return
        existing_record = await entity_service.get_entity(section, int(entity_id_raw))
        if not existing_record:
            await callback.message.answer("Entity not found.")
            return

        if status == "ACTIVE":
            verified, reason = await _verify_bot_chat_access(
                callback.bot,
                section,
                existing_record.chat_identifier,
            )
            if not verified:
                await _safe_edit_or_reply(
                    callback,
                    _review_text(
                        section,
                        existing_record.id,
                        existing_record.chat_identifier,
                        existing_record.title,
                        existing_record.status,
                    )
                    + f"\n\n{reason}",
                    build_entity_review_keyboard(section, existing_record.id),
                )
                return

        record = await entity_service.update_status(section, int(entity_id_raw), status)
        if not record:
            await callback.message.answer("Entity not found.")
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="ENTITY_STATUS_UPDATE",
            target_type=section,
            target_id=f"{record.id}:{status}",
            details=record.chat_identifier,
        )
        suffix = ""
        if status == "ACTIVE":
            suffix = "\n\nVerified and activated."
        await _safe_edit_or_reply(
            callback,
            _review_text(section, record.id, record.chat_identifier, record.title, record.status) + suffix,
            None,
        )
        await callback.message.answer(
            "Review updated. You can continue from here.",
            reply_markup=build_success_next_keyboard("review_done" if section == "Channels" else "review_done_groups"),
        )

    @router.callback_query(F.data.startswith("reviewopen:"))
    async def review_open_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return

        _, section, entity_id_raw = callback.data.split(":", maxsplit=2)
        if not can_run_section_action(profile, section, "Pending"):
            await callback.answer("You do not have access to review items.", show_alert=True)
            return

        record = await entity_service.get_entity(section, int(entity_id_raw))
        if not record:
            await callback.answer("Item not found", show_alert=True)
            return

            await callback.answer("Review card ready")
        await _safe_edit_or_reply(
            callback,
            _review_text(section, record.id, record.chat_identifier, record.title, record.status),
            build_entity_review_keyboard(section, record.id),
        )

    @router.callback_query(F.data.startswith("postconfirm:"))
    async def post_confirm_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        pending_post = await posting_service.get_pending_post(callback.from_user.id)
        if not pending_post or pending_post.stage != "await_confirm":
            await callback.answer("No open post draft right now.", show_alert=True)
            return

        _, action = callback.data.split(":", maxsplit=1)
        if action == "cancel":
            await posting_service.clear_pending_post(callback.from_user.id)
            await callback.answer("Post draft cleared")
            await _safe_edit_or_reply(
                callback,
                "❌ Post draft canceled.",
                None,
            )
            await callback.message.answer(
                "You can start again anytime from 📝 New Post.",
                reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(callback.from_user.id)),
            )
            return

        sent = await send_stored_content(
            callback.bot,
            pending_post.channel_identifier,
            pending_post.draft_message_text,
            pending_post.draft_media_path,
            pending_post.draft_media_name,
            pending_post.draft_media_type,
        )
        await posting_service.clear_pending_post(callback.from_user.id)
        details = f"message_id={sent.message_id}"
        if pending_post.draft_media_path:
            details += "|media=1"
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="POST_CHANNEL_MESSAGE",
            target_type="CHANNEL",
            target_id=pending_post.channel_identifier,
            details=details,
        )
        await callback.answer("Posted")
        await _safe_edit_or_reply(
            callback,
            f"✅ Posted to {pending_post.channel_title or pending_post.channel_identifier}.",
            None,
        )
        await callback.message.answer(
            "✅ Post sent.",
            reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(callback.from_user.id)),
        )
        await callback.message.answer(
            "What would you like to do next?",
            reply_markup=build_success_next_keyboard("post_sent"),
        )

    @router.callback_query(F.data.startswith("broadcastconfirm:"))
    async def broadcast_confirm_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not can_access_admin_ui(profile):
            await callback.answer("You do not have access to this action.", show_alert=True)
            return
        pending_broadcast = await posting_service.get_pending_broadcast(callback.from_user.id)
        if not pending_broadcast or pending_broadcast.stage != "await_confirm":
            await callback.answer("No open broadcast draft right now.", show_alert=True)
            return

        _, action = callback.data.split(":", maxsplit=1)
        if action == "cancel":
            await posting_service.clear_pending_broadcast(callback.from_user.id)
            await callback.answer("Broadcast draft cleared")
            await _safe_edit_or_reply(
                callback,
                "❌ Broadcast draft canceled.",
                None,
            )
            await callback.message.answer(
                "You can start again anytime from 📤 Broadcast.",
                reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(callback.from_user.id)),
            )
            return

        success_count = 0
        failed_targets: list[str] = []
        for target in pending_broadcast.targets:
            identifier = target["channel_identifier"]
            title = target.get("channel_title")
            try:
                sent = await send_stored_content(
                    callback.bot,
                    identifier,
                    pending_broadcast.draft_message_text,
                    pending_broadcast.draft_media_path,
                    pending_broadcast.draft_media_name,
                    pending_broadcast.draft_media_type,
                )
                success_count += 1
                details = f"message_id={sent.message_id}"
                if pending_broadcast.draft_media_path:
                    details += "|media=1"
                await access_service.record_event(
                    actor_user_id=profile.user.id,
                    action_key="BROADCAST_CHANNEL_MESSAGE",
                    target_type="CHANNEL",
                    target_id=identifier,
                    details=details,
                )
            except TelegramBadRequest:
                failed_targets.append(title or identifier)

        await posting_service.clear_pending_broadcast(callback.from_user.id)
        summary = f"✅ Broadcast complete. Success: {success_count}/{len(pending_broadcast.targets)}"
        if failed_targets:
            summary += "\nFailed: " + ", ".join(failed_targets[:10])
        await callback.answer("Broadcast sent")
        await _safe_edit_or_reply(callback, summary, None)
        await callback.message.answer(
            "✅ Broadcast sent.",
            reply_markup=_menu_keyboard_for_profile(profile, await ui_preferences_service.get_mode(callback.from_user.id)),
        )
        await callback.message.answer(
            "What would you like to do next?",
            reply_markup=build_success_next_keyboard("broadcast_sent"),
        )

    @router.my_chat_member()
    async def bot_chat_membership_handler(event: ChatMemberUpdated) -> None:
        section = _chat_section(event.chat.type)
        if not section:
            return

        new_status = event.new_chat_member.status
        if new_status in {"left", "kicked"}:
            removed = await entity_service.mark_removed(section, _chat_identifier(event.chat))
            if removed:
                for owner_id in app_context.settings.owner_ids:
                    try:
                        await event.bot.send_message(
                            owner_id,
                            _review_text(
                                section,
                                removed.id,
                                removed.chat_identifier,
                                removed.title,
                                removed.status,
                            ) + "\n\nBot was removed from this chat.",
                            reply_markup=build_entity_review_keyboard(section, removed.id),
                        )
                    except Exception:
                        continue
            return

        if new_status not in {"administrator", "member"}:
            return

        if event.old_chat_member.status == new_status:
            return

        added_by_user_id = None
        user_found = False
        if event.from_user:
            def _get_db_user_id(tg_id):
                with app_context.oracle_client.connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_id", {"tg_id": tg_id})
                        row = cur.fetchone()
                        return row[0] if row else None
            try:
                added_by_user_id = await asyncio.to_thread(_get_db_user_id, event.from_user.id)
                if added_by_user_id is not None:
                    user_found = True
            except Exception:
                logger.exception("Failed to query DB user ID for telegram user %s", event.from_user.id)

        if user_found:
            record = await entity_service.detect_entity(
                section,
                _chat_identifier(event.chat),
                getattr(event.chat, "title", None),
                added_by_user_id=added_by_user_id,
                status="ACTIVE",
            )
            if record and event.from_user:
                try:
                    chat_type_label = "চ্যানেলটি" if section == "Channels" else "গ্রুপটি"
                    chat_name = record.title or record.chat_identifier
                    message_text = (
                        f"🎉 <b>অভিনন্দন!</b>\n\n"
                        f"আপনার {chat_type_label} <b>{chat_name}</b> সফলভাবে বটের সাথে কানেক্ট করা হয়েছে এবং এটি এখন সম্পূর্ণ সক্রিয় (ACTIVE)।\n\n"
                        f"🤖 এখন থেকে আপনি এই এআই ম্যানেজারের চ্যাটে গিয়ে বলতে পারেন—যেমন:\n"
                        f"• <i>'এই পোস্টটি {chat_name} চ্যানেলে দাও'</i>\n"
                        f"• <i>'একটি অফার পোস্ট কাল সকাল ১০ টায় {chat_name} এ শিডিউল করো'</i>"
                    )
                    await event.bot.send_message(
                        event.from_user.id,
                        message_text,
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.exception("Failed to send auto-activation message to user %s", event.from_user.id)
            return

        record = await entity_service.detect_entity(
            section,
            _chat_identifier(event.chat),
            getattr(event.chat, "title", None),
        )
        if not record:
            return

        for owner_id in app_context.settings.owner_ids:
            try:
                await event.bot.send_message(
                    owner_id,
                    _review_text(section, record.id, record.chat_identifier, record.title, record.status),
                    reply_markup=build_entity_review_keyboard(section, record.id),
                )
            except Exception:
                continue

    @router.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"^/(warn|unwarn|warnings)(?:@[\w_]+)?(?:\s|$)"))
    async def group_warning_command_handler(message: Message) -> None:
        if not message.from_user:
            return

        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        if not await _is_group_admin(message.bot, message.chat.id, message.from_user.id):
            await message.reply("Only group admins can use warning commands.")
            return

        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply("Reply to a member's message with /warn, /unwarn, or /warnings.")
            return

        target_user = message.reply_to_message.from_user
        if target_user.is_bot:
            await message.reply("Warnings are only for human members.")
            return

        if await _is_group_admin(message.bot, message.chat.id, target_user.id):
            await message.reply("Admins cannot be warned with this flow.")
            return

        command = (message.text or "").split()[0].split("@")[0].lower()
        group_key = _warning_group_key(active_group)
        member_label = _build_member_label(target_user)

        if command == "/warnings":
            count = await warning_service.get_warning_count(group_key, target_user.id)
            await message.reply(f"{member_label} has {count} warning(s).")
            return

        admin_profile = await access_service.build_access_profile(message.from_user)

        if command == "/unwarn":
            count = await warning_service.decrement_warning(group_key, target_user.id, member_label)
            await access_service.record_event(
                actor_user_id=admin_profile.user.id,
                action_key="UNWARN_MEMBER",
                target_type="GROUP_MEMBER",
                target_id=f"{message.chat.id}:{target_user.id}",
                details=f"remaining={count}",
            )
            await message.reply(f"{member_label} now has {count} warning(s).")
            return

        count = await warning_service.increment_warning(group_key, target_user.id, member_label)
        await access_service.record_event(
            actor_user_id=admin_profile.user.id,
            action_key="WARN_MEMBER",
            target_type="GROUP_MEMBER",
            target_id=f"{message.chat.id}:{target_user.id}",
            details=f"count={count}",
        )

        if count >= 3:
            try:
                await message.bot.restrict_chat_member(
                    message.chat.id,
                    target_user.id,
                    permissions=_locked_permissions(),
                    until_date=datetime.utcnow() + timedelta(hours=24),
                )
                await message.reply(
                    f"{member_label} reached {count} warnings and has been muted for 24 hours."
                )
                await access_service.record_event(
                    actor_user_id=admin_profile.user.id,
                    action_key="AUTO_MUTE_WARN_THRESHOLD",
                    target_type="GROUP_MEMBER",
                    target_id=f"{message.chat.id}:{target_user.id}",
                    details="hours=24 threshold=3",
                )
                return
            except TelegramBadRequest as exc:
                await message.reply(
                    f"{member_label} reached {count} warnings, but mute failed: {exc.message}"
                )
                return

        await message.reply(f"{member_label} now has {count} warning(s).")

    @router.message(
        F.chat.type.in_({"group", "supergroup"}),
        F.text.regexp(r"^/(addbadword|removebadword|badwords)(?:@[\w_]+)?(?:\s|$)"),
    )
    async def group_filter_admin_command_handler(message: Message) -> None:
        if not message.from_user:
            return

        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        if not await _is_group_admin(message.bot, message.chat.id, message.from_user.id):
            await message.reply("Only group admins can manage filters.")
            return

        command_parts = (message.text or "").split(maxsplit=1)
        command = command_parts[0].split("@")[0].lower()
        argument = command_parts[1].strip().lower() if len(command_parts) > 1 else ""
        group_key = _warning_group_key(active_group)

        if command == "/badwords":
            state = await filter_service.get_state(group_key)
            custom = ", ".join(state.custom_bad_words) if state.custom_bad_words else "None"
            await message.reply(f"Custom bad words: {custom}")
            return

        if not argument:
            await message.reply("Provide a word. Example: /addbadword scam")
            return

        admin_profile = await access_service.build_access_profile(message.from_user)
        if command == "/addbadword":
            state = await filter_service.add_bad_word(group_key, argument)
            await access_service.record_event(
                actor_user_id=admin_profile.user.id,
                action_key="ADD_GROUP_BAD_WORD",
                target_type="GROUP",
                target_id=active_group.chat_identifier,
                details=argument,
            )
            await message.reply(f"Added bad word. Custom list size: {len(state.custom_bad_words)}")
            return

        state = await filter_service.remove_bad_word(group_key, argument)
        await access_service.record_event(
            actor_user_id=admin_profile.user.id,
            action_key="REMOVE_GROUP_BAD_WORD",
            target_type="GROUP",
            target_id=active_group.chat_identifier,
            details=argument,
        )
        await message.reply(f"Removed bad word. Custom list size: {len(state.custom_bad_words)}")

    @router.message(
        F.chat.type.in_({"group", "supergroup"}),
        F.text.regexp(r"^/(setwelcome|showwelcome)(?:@[\w_]+)?(?:\s|$)"),
    )
    async def group_welcome_admin_command_handler(message: Message) -> None:
        if not message.from_user:
            return

        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        if not await _is_group_admin(message.bot, message.chat.id, message.from_user.id):
            await message.reply("Only group admins can manage welcome settings.")
            return

        command_parts = (message.text or "").split(maxsplit=1)
        command = command_parts[0].split("@")[0].lower()
        group_key = _warning_group_key(active_group)

        if command == "/showwelcome":
            state = await group_event_service.get_state(group_key)
            await message.reply(
                _welcome_panel_text(active_group.title or active_group.chat_identifier, state)
            )
            return

        if len(command_parts) < 2 or not command_parts[1].strip():
            await message.reply("Usage: /setwelcome Welcome {member} to {group}")
            return

        admin_profile = await access_service.build_access_profile(message.from_user)
        state = await group_event_service.set_welcome_template(group_key, command_parts[1].strip())
        await access_service.record_event(
            actor_user_id=admin_profile.user.id,
            action_key="SET_GROUP_WELCOME_TEMPLATE",
            target_type="GROUP",
            target_id=active_group.chat_identifier,
            details=command_parts[1].strip()[:120],
        )
        await message.reply(
            _welcome_panel_text(active_group.title or active_group.chat_identifier, state)
        )

    @router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
    async def group_filter_enforcement_handler(message: Message) -> None:
        if not message.from_user or message.from_user.is_bot:
            return

        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        if await _is_group_admin(message.bot, message.chat.id, message.from_user.id):
            return

        state = await filter_service.get_state(_warning_group_key(active_group))
        text = message.text or ""
        delete_reason = None

        if state.anti_link_enabled and filter_service.contains_link(text):
            delete_reason = "Links are not allowed in this group."
        elif state.bad_word_enabled:
            matched_word = filter_service.contains_bad_word(text, state.effective_bad_words)
            if matched_word:
                delete_reason = f"Filtered word detected: {matched_word}"

        if not delete_reason:
            return

        try:
            await message.delete()
        except TelegramBadRequest:
            return

        await warning_service.increment_warning(
            _warning_group_key(active_group),
            message.from_user.id,
            _build_member_label(message.from_user),
        )
        await access_service.record_event(
            actor_user_id=None,
            action_key="AUTO_FILTER_DELETE",
            target_type="GROUP_MESSAGE",
            target_id=f"{message.chat.id}:{message.message_id}",
            details=delete_reason,
        )
        try:
            await message.answer(delete_reason)
        except TelegramBadRequest:
            return

    @router.message(F.chat.type.in_({"group", "supergroup"}), F.new_chat_members)
    async def group_new_members_handler(message: Message) -> None:
        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        state = await group_event_service.get_state(_warning_group_key(active_group))
        group_label = active_group.title or active_group.chat.title or active_group.chat_identifier

        for member in message.new_chat_members:
            if member.is_bot:
                continue
            member_label = _build_member_label(member)
            if state.join_log_enabled:
                try:
                    await message.answer(f"{member_label} joined {group_label}.")
                except TelegramBadRequest:
                    pass
            if state.welcome_enabled:
                try:
                    await message.answer(
                        group_event_service.render_welcome(
                            state.welcome_template,
                            member_label,
                            group_label,
                        )
                    )
                except TelegramBadRequest:
                    pass

    @router.message(F.chat.type.in_({"group", "supergroup"}), F.left_chat_member)
    async def group_left_member_handler(message: Message) -> None:
        active_group = await _resolve_active_group_record(entity_service, message.chat)
        if not active_group:
            return

        state = await group_event_service.get_state(_warning_group_key(active_group))
        if not state.join_log_enabled:
            return

        member = message.left_chat_member
        if not member or member.is_bot:
            return

        try:
            await message.answer(f"{_build_member_label(member)} left {active_group.title or active_group.chat_identifier}.")
        except TelegramBadRequest:
            return

    return router
