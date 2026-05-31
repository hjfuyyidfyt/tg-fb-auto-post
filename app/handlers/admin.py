from __future__ import annotations

import asyncio
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.runtime import AppContext
from app.db.redis_client import build_redis_client
from app.keyboards.section_actions import build_access_request_review_keyboard
from app.services.access import AccessService
from app.services.auth import can_access_admin_ui, is_owner
from app.services.access_requests import AccessRequestService, REQUESTABLE_ROLE_KEYS
from app.services.facebook_promo_ai import FacebookPromoAIService
from app.services.login_codes import LoginCodeService
from app.services.roles import RoleManagementService

router = Router(name="admin")


def _parse_grant_command(text: str) -> tuple[int, str] | None:
    parts = text.split()
    if len(parts) != 3:
        return None

    _, telegram_user_id_raw, role_key = parts
    try:
        telegram_user_id = int(telegram_user_id_raw)
    except ValueError:
        return None
    return telegram_user_id, role_key.upper()


def _parse_revoke_command(text: str) -> tuple[int, str] | None:
    return _parse_grant_command(text)


def _parse_request_command(text: str) -> str | None:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    role_key = parts[1].strip().upper()
    if role_key not in REQUESTABLE_ROLE_KEYS:
        return None
    return role_key


def _format_user_role_summary(summary) -> str:
    label = summary.display_name or summary.username or str(summary.telegram_user_id)
    username = f"@{summary.username}" if summary.username else "-"
    roles = ", ".join(summary.role_keys) if summary.role_keys else "No roles"
    return (
        f"{label}\n"
        f"Telegram ID: {summary.telegram_user_id}\n"
        f"Username: {username}\n"
        f"Roles: {roles}"
    )


def _help_text(is_owner_user: bool) -> str:
    common_lines = [
        "📘 Help",
        "",
        "Best starting points:",
        "- /start -> open the main menu",
        "- /help -> show this guide",
        "- /ping -> check bot response health",
        "- /cancel -> leave the current draft/flow",
        "- /login_code -> get a dashboard login code",
        "- /schedule_list -> review schedules",
        "",
        "Fast paths in the bot:",
        "- ⚡ Create -> post, schedule, broadcast, add a target",
        "- ✅ Review -> pending channels, groups, schedules, alerts",
        "- 📊 Status -> channels, groups, bots, reports",
        "- ⚙️ More -> automation, settings, and deeper tools",
        "- 🧭 Mode -> switch between Simple and Pro",
        "",
        "Profile commands:",
        "- /my_roles",
        "- /whoami",
    ]
    if is_owner_user:
        common_lines.extend(
            [
                "",
                "Owner commands:",
                "- /roles",
                "- /grant_role <telegram_user_id> <ROLE_KEY>",
                "- /revoke_role <telegram_user_id> <ROLE_KEY>",
                "- /user_roles <telegram_user_id>",
                "- /admins",
                "- /pending_access",
                "- /promo_live_check",
                "- /facebook_config",
                "- /image_config",
                "- /image_live_test CONFIRM",
                "- /image_usage [telegram_user_id]",
                "- /reset_image_usage <telegram_user_id|global>",
            ]
        )
    else:
        common_lines.extend(
            [
                "",
                "Access request:",
                "- /request_access <VIEWER|CHANNEL_MANAGER|GROUP_MANAGER|MODERATOR>",
            ]
        )
    return "\n".join(common_lines)


def register_admin_handlers(app_context: AppContext) -> Router:
    access_service = AccessService(app_context)
    role_service = RoleManagementService(app_context)
    redis_client = build_redis_client(app_context.settings)
    access_request_service = AccessRequestService(redis_client)
    login_code_service = LoginCodeService(redis_client)
    facebook_promo_service = FacebookPromoAIService(
        redis_client=redis_client,
        graph_api_enabled=app_context.settings.facebook_promo_graph_api_enabled,
        graph_version=app_context.settings.facebook_graph_version,
        alibaba_api_key=app_context.settings.alibaba_api_key,
        alibaba_image_api_enabled=app_context.settings.alibaba_image_api_enabled,
        alibaba_image_dry_run=app_context.settings.alibaba_image_dry_run,
        alibaba_image_admin_live_only=app_context.settings.alibaba_image_admin_live_only,
        alibaba_image_base_url=app_context.settings.alibaba_image_base_url,
        alibaba_free_monthly_image_cap=app_context.settings.alibaba_free_monthly_image_cap,
        alibaba_paid_monthly_image_cap=app_context.settings.alibaba_paid_monthly_image_cap,
        alibaba_global_monthly_image_cap=app_context.settings.alibaba_global_monthly_image_cap,
    )

    @router.message(Command("roles"))
    async def list_roles_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect role setup right now.")
            return

        roles = await role_service.list_roles()
        if not roles:
            await message.answer("Oracle is not configured yet, so roles cannot be loaded.")
            return

        lines = [f"- {role.role_key} -> {role.role_name}" for role in roles]
        await message.answer("Available roles\n\n" + "\n".join(lines))

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer(
                "This bot is for approved admins only.\n\n"
                "If you need access, use:\n"
                "/request_access VIEWER"
            )
            return
        await message.answer(_help_text(is_owner(profile)))

    @router.message(Command("ping"))
    async def ping_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            return

        started = time.perf_counter()
        redis_started = time.perf_counter()
        redis_ok = True
        redis_error = ""
        try:
            await asyncio.to_thread(redis_client.ping)
        except Exception as exc:
            redis_ok = False
            redis_error = str(exc)[:120]
        redis_ms = round((time.perf_counter() - redis_started) * 1000)
        total_ms = round((time.perf_counter() - started) * 1000)
        await message.answer(
            "Bot health\n\n"
            f"Handler check: {total_ms} ms\n"
            f"Redis: {'OK' if redis_ok else 'ERROR'} ({redis_ms} ms)"
            + (f"\nRedis error: {redis_error}" if redis_error else "")
        )

    @router.message(Command("request_access"))
    async def request_access_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if profile.role_keys:
            await message.answer("You already have an access role for this bot.")
            return

        role_key = _parse_request_command(message.text or "")
        if not role_key:
            await message.answer("Try like this:\n/request_access VIEWER")
            return

        existing = await access_request_service.get_request(message.from_user.id)
        if existing and existing.status == "PENDING":
            await message.answer(f"You already have a pending access request for {existing.role_key}.")
            return

        request = await access_request_service.create_request(
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            display_name=message.from_user.full_name,
            role_key=role_key,
        )
        await access_service.record_event(
            actor_user_id=message.from_user.id,
            action_key="REQUEST_ACCESS",
            target_type="USER_ROLE",
            target_id=f"{request.telegram_user_id}:{request.role_key}",
        )
        requester_label = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "-"
        text = (
            "Access request\n\n"
            f"Name: {requester_label}\n"
            f"Telegram ID: {request.telegram_user_id}\n"
            f"Username: {username}\n"
            f"Requested role: {request.role_key}"
        )
        for owner_id in app_context.settings.owner_ids:
            try:
                await message.bot.send_message(
                    owner_id,
                    text,
                    reply_markup=build_access_request_review_keyboard(request.telegram_user_id, request.role_key),
                )
            except Exception:
                continue
        await message.answer(f"Access request submitted for {request.role_key}.")

    @router.message(Command("pending_access"))
    async def pending_access_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect pending access requests.")
            return

        pending = await access_request_service.list_pending()
        if not pending:
            await message.answer("There are no pending access requests right now.")
            return

        lines = ["Pending access requests", ""]
        for item in pending[:20]:
            label = item.display_name or item.username or str(item.telegram_user_id)
            username = f"@{item.username}" if item.username else "-"
            lines.append(f"- {label} | {item.telegram_user_id} | {username} | {item.role_key}")
        await message.answer("\n".join(lines))

    @router.message(Command("my_roles"))
    async def my_roles_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        roles = ", ".join(sorted(profile.role_keys)) if profile.role_keys else "No roles"
        username = f"@{message.from_user.username}" if message.from_user.username else "-"
        await message.answer(
            "Your access profile\n\n"
            f"Telegram ID: {message.from_user.id}\n"
            f"Username: {username}\n"
            f"Roles: {roles}"
        )

    @router.message(Command("whoami"))
    async def whoami_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        roles = ", ".join(sorted(profile.role_keys)) if profile.role_keys else "No roles"
        username = f"@{message.from_user.username}" if message.from_user.username else "-"
        await message.answer(
            "Who am I\n\n"
            f"Telegram ID: {message.from_user.id}\n"
            f"Username: {username}\n"
            f"Name: {message.from_user.full_name}\n"
            f"Roles: {roles}"
        )

    @router.message(Command("login_code"))
    async def login_code_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not can_access_admin_ui(profile):
            await message.answer("Only approved admins can generate dashboard login codes.")
            return

        code = await login_code_service.issue_code(message.from_user.id)
        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="ISSUE_LOGIN_CODE",
            target_type="WEB_LOGIN",
            target_id=str(message.from_user.id),
        )
        await message.answer(
            "Dashboard login code\n\n"
            f"URL:\n<code>{app_context.settings.dashboard_public_url}</code>\n\n"
            f"Telegram ID:\n<code>{message.from_user.id}</code>\n\n"
            f"Code:\n<code>{code}</code>\n\n"
            "This code expires in 10 minutes and works once.",
            parse_mode="HTML",
        )

    @router.message(Command("admins"))
    async def admins_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect admin assignments.")
            return

        users = await role_service.list_users_with_roles()
        if not users:
            await message.answer("No assigned role users found yet.")
            return

        lines = []
        for summary in users[:25]:
            label = summary.display_name or summary.username or str(summary.telegram_user_id)
            roles = ", ".join(summary.role_keys) if summary.role_keys else "No roles"
            lines.append(f"- {label} ({summary.telegram_user_id}) -> {roles}")
        await message.answer("Assigned users\n\n" + "\n".join(lines))

    @router.message(Command("image_usage"))
    async def image_usage_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect image usage.")
            return

        parts = (message.text or "").split()
        if len(parts) > 2:
            await message.answer("Try like this:\n/image_usage [telegram_user_id]")
            return
        target_id = message.from_user.id
        if len(parts) == 2:
            try:
                target_id = int(parts[1])
            except ValueError:
                await message.answer("Telegram user id must be numeric.")
                return

        user_count = await facebook_promo_service.get_monthly_image_usage(target_id)
        global_count = await facebook_promo_service.get_global_monthly_image_usage()
        target_summary = await role_service.get_user_role_summary(target_id)
        target_role_keys = set(target_summary.role_keys) if target_summary else set()
        policy = await facebook_promo_service.build_image_generation_policy(target_id, target_role_keys)
        await message.answer(
            "Facebook Promo image usage\n\n"
            f"Target Telegram ID: {target_id}\n"
            f"Target tier: {policy.user_tier}\n"
            f"Target monthly usage: {user_count}/{policy.monthly_limit}\n"
            f"Global monthly usage: {global_count}/{facebook_promo_service.alibaba_global_monthly_image_cap}\n"
            f"API enabled: {'YES' if facebook_promo_service.alibaba_image_api_enabled else 'NO'}\n"
            f"Dry-run: {'ON' if facebook_promo_service.alibaba_image_dry_run else 'OFF'}\n"
            f"Admin-only live rollout: {'ON' if facebook_promo_service.alibaba_image_admin_live_only else 'OFF'}\n"
            f"Default model for your role: {policy.model or 'Blocked'}"
        )

    @router.message(Command("image_config"))
    async def image_config_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect image generation config.")
            return

        free_order = ", ".join(FacebookPromoAIService.image_model_order_for_tier("FREE"))
        paid_order = ", ".join(FacebookPromoAIService.image_model_order_for_tier("PAID"))
        admin_order = ", ".join(FacebookPromoAIService.image_model_order_for_tier("ADMIN"))
        rankings = "\n".join(
            f"{rank}. {model} - {note}"
            for rank, model, note in FacebookPromoAIService.image_model_rankings()
        )
        preflight = await facebook_promo_service.build_image_live_preflight(message.from_user.id, profile.role_keys)
        preflight_text = "\n".join(preflight.checks)
        blocker_text = "\n".join(f"- {item}" for item in preflight.blockers) if preflight.blockers else "- none"
        await message.answer(
            "Facebook Promo image config\n\n"
            f"API key loaded: {'YES' if bool(app_context.settings.alibaba_api_key) else 'NO'}\n"
            f"API enabled: {'YES' if facebook_promo_service.alibaba_image_api_enabled else 'NO'}\n"
            f"Dry-run: {'ON' if facebook_promo_service.alibaba_image_dry_run else 'OFF'}\n"
            f"Admin-only live rollout: {'ON' if facebook_promo_service.alibaba_image_admin_live_only else 'OFF'}\n"
            f"Free monthly cap: {facebook_promo_service.alibaba_free_monthly_image_cap}\n"
            f"Paid/Admin monthly cap: {facebook_promo_service.alibaba_paid_monthly_image_cap}\n"
            f"Global monthly cap: {facebook_promo_service.alibaba_global_monthly_image_cap}\n\n"
            f"Free model order:\n{free_order}\n\n"
            f"Paid model order:\n{paid_order}\n\n"
            f"Admin safe-test model order:\n{admin_order}\n\n"
            f"Ranked models:\n{rankings}\n\n"
            f"Live-test ready: {'YES' if preflight.ready else 'NO'}\n"
            f"Preflight checks:\n{preflight_text}\n\n"
            f"Preflight blockers:\n{blocker_text}\n\n"
            "Safe live-test requirement: enable API, turn dry-run OFF, keep admin-only ON, then test exactly one image."
        )

    @router.message(Command("image_live_test"))
    async def image_live_test_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can run an image live test.")
            return

        parts = (message.text or "").split()
        confirmed = len(parts) == 2 and parts[1] == "CONFIRM"
        requested_model = "z-image-turbo"
        preflight = await facebook_promo_service.build_image_live_preflight(
            message.from_user.id,
            profile.role_keys,
            requested_model,
        )
        blockers = "\n".join(f"- {item}" for item in preflight.blockers) if preflight.blockers else "- none"
        checks = "\n".join(preflight.checks)
        if not confirmed:
            await message.answer(
                "One-image live test is armed, not executed.\n\n"
                "No Alibaba API call was made.\n\n"
                f"Requested model: {requested_model}\n\n"
                f"Checks:\n{checks}\n\n"
                f"Blockers:\n{blockers}\n\n"
                "To run exactly one live test after fixing blockers, send:\n"
                "/image_live_test CONFIRM"
            )
            return

        if not preflight.ready:
            await message.answer(
                "Image live test blocked.\n\n"
                "No Alibaba API call was made.\n\n"
                f"Requested model: {requested_model}\n\n"
                f"Checks:\n{checks}\n\n"
                f"Blockers:\n{blockers}"
            )
            return

        policy = await facebook_promo_service.build_image_generation_policy(
            message.from_user.id,
            profile.role_keys,
            requested_model,
        )
        prompt = (
            "Create one clean square promotional image for a small business social media post. "
            "Use a polished product-ad style, no text overlay, no logo, simple background, high quality."
        )
        result = await facebook_promo_service.image_adapter.generate(policy.model or requested_model, prompt)
        if result.ok and result.image_urls:
            user_count, global_count = await facebook_promo_service.record_successful_image_generation(message.from_user.id)
            await message.answer(
                "One-image live test completed.\n\n"
                f"Model: {policy.model or requested_model}\n"
                f"Usage after test: user {user_count}/{policy.monthly_limit}, global {global_count}/{policy.global_limit}\n"
                f"Image URL:\n{result.image_urls[0]}"
            )
            return

        await message.answer(
            "One-image live test did not return a usable image.\n\n"
            f"Model: {policy.model or requested_model}\n"
            f"Status code: {result.status_code or 'n/a'}\n"
            f"Message: {result.message}\n"
            "Usage was not incremented because no image URL was returned."
        )

    @router.message(Command("facebook_config"))
    async def facebook_config_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect Facebook publish config.")
            return

        status = await facebook_promo_service.build_publish_safety_status(message.from_user.id)
        checks = "\n".join(status.checks)
        blockers = "\n".join(f"- {item}" for item in status.blockers) if status.blockers else "- none"
        await message.answer(
            "Facebook Promo publish config\n\n"
            f"Live publish ready: {'YES' if status.live_enabled and status.access_ready and not status.blockers else 'NO'}\n\n"
            f"Checks:\n{checks}\n\n"
            f"Blockers:\n{blockers}\n\n"
            "Safe rollout rule: use Dry Run Publish first. Only enable live Graph API after Page access validates."
        )

    @router.message(Command("promo_live_check"))
    async def promo_live_check_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect the Facebook Promo live-test checklist.")
            return

        image_preflight = await facebook_promo_service.build_image_live_preflight(
            message.from_user.id,
            profile.role_keys,
        )
        facebook_status = await facebook_promo_service.build_publish_safety_status(message.from_user.id)
        image_blockers = "\n".join(f"- {item}" for item in image_preflight.blockers) if image_preflight.blockers else "- none"
        facebook_blockers = "\n".join(f"- {item}" for item in facebook_status.blockers) if facebook_status.blockers else "- none"
        image_checks = "\n".join(image_preflight.checks)
        facebook_checks = "\n".join(facebook_status.checks)
        await message.answer(
            "Facebook Promo live-test checklist\n\n"
            f"Image live test ready: {'YES' if image_preflight.ready else 'NO'}\n"
            f"Facebook live publish ready: {'YES' if facebook_status.live_enabled and facebook_status.access_ready and not facebook_status.blockers else 'NO'}\n\n"
            "Image checks:\n"
            f"{image_checks}\n\n"
            "Image blockers:\n"
            f"{image_blockers}\n\n"
            "Facebook checks:\n"
            f"{facebook_checks}\n\n"
            "Facebook blockers:\n"
            f"{facebook_blockers}\n\n"
            "Safe rollout order:\n"
            "1. Keep Alibaba admin-only ON and test exactly one low-tier image.\n"
            "2. Save and dry-run validate Facebook Page access.\n"
            "3. Dry-run publish a ready campaign.\n"
            "4. Use final confirmation for one controlled live Facebook post.\n\n"
            "No live API call is made by this command."
        )

    @router.message(Command("reset_image_usage"))
    async def reset_image_usage_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can reset image usage.")
            return

        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Try like this:\n/reset_image_usage <telegram_user_id|global>")
            return
        target = parts[1].strip().lower()
        if target == "global":
            await facebook_promo_service.reset_global_monthly_image_usage()
            await message.answer("Global monthly image usage counter was reset.")
            return
        try:
            target_id = int(target)
        except ValueError:
            await message.answer("Target must be a Telegram user id or global.")
            return
        await facebook_promo_service.reset_monthly_image_usage(target_id)
        await message.answer(f"Monthly image usage counter reset for Telegram user {target_id}.")

    @router.message(Command("user_roles"))
    async def user_roles_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can inspect another user's roles.")
            return

        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Try like this:\n/user_roles <telegram_user_id>")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("Telegram user id must be numeric.")
            return

        summary = await role_service.get_user_role_summary(target_id)
        if not summary:
            await message.answer("User not found in Oracle yet.")
            return
        await message.answer(_format_user_role_summary(summary))

    @router.message(Command("grant_role"))
    async def grant_role_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can grant roles.")
            return

        parsed = _parse_grant_command(message.text or "")
        if not parsed:
            await message.answer("Try like this:\n/grant_role <telegram_user_id> <ROLE_KEY>")
            return

        telegram_user_id, role_key = parsed
        user = await role_service.grant_role_by_telegram_id(telegram_user_id, role_key)
        if not user:
            await message.answer("Oracle is not configured yet, so roles cannot be granted.")
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="GRANT_ROLE",
            target_type="USER_ROLE",
            target_id=f"{telegram_user_id}:{role_key}",
        )
        await message.answer(f"Granted {role_key} to Telegram user {telegram_user_id}.")

    @router.message(Command("revoke_role"))
    async def revoke_role_handler(message: Message) -> None:
        profile = await access_service.build_access_profile(message.from_user)
        if not is_owner(profile):
            await message.answer("Only the owner can revoke roles.")
            return

        parsed = _parse_revoke_command(message.text or "")
        if not parsed:
            await message.answer("Try like this:\n/revoke_role <telegram_user_id> <ROLE_KEY>")
            return

        telegram_user_id, role_key = parsed
        user = await role_service.revoke_role_by_telegram_id(telegram_user_id, role_key)
        if not user:
            await message.answer("User not found in Oracle yet, so nothing was revoked.")
            return

        await access_service.record_event(
            actor_user_id=profile.user.id,
            action_key="REVOKE_ROLE",
            target_type="USER_ROLE",
            target_id=f"{telegram_user_id}:{role_key}",
        )
        await message.answer(f"Revoked {role_key} from Telegram user {telegram_user_id}.")

    @router.callback_query(F.data.startswith("accessreq:"))
    async def access_request_review_callback(callback: CallbackQuery) -> None:
        profile = await access_service.build_access_profile(callback.from_user)
        if not is_owner(profile):
            await callback.answer("Only the owner can review access requests.", show_alert=True)
            return

        _, telegram_user_id_raw, role_key, status = callback.data.split(":", maxsplit=3)
        telegram_user_id = int(telegram_user_id_raw)
        request = await access_request_service.get_request(telegram_user_id)
        if not request or request.status != "PENDING":
            await callback.answer("This request was already handled or is no longer available.", show_alert=True)
            return

        updated = await access_request_service.update_status(telegram_user_id, status)
        if status == "APPROVED":
            await role_service.grant_role_by_telegram_id(telegram_user_id, role_key)
            await access_service.record_event(
                actor_user_id=profile.user.id,
                action_key="APPROVE_ACCESS_REQUEST",
                target_type="USER_ROLE",
                target_id=f"{telegram_user_id}:{role_key}",
            )
            try:
                await callback.bot.send_message(
                    telegram_user_id,
                    f"Your access request was approved. Assigned role: {role_key}",
                )
            except Exception:
                pass
        else:
            await access_service.record_event(
                actor_user_id=profile.user.id,
                action_key="REJECT_ACCESS_REQUEST",
                target_type="USER_ROLE",
                target_id=f"{telegram_user_id}:{role_key}",
            )
            try:
                await callback.bot.send_message(
                    telegram_user_id,
                    f"Your access request for {role_key} was rejected.",
                )
            except Exception:
                pass

        await callback.answer(f"Request {status.lower()}")
        await callback.message.edit_text(
            callback.message.text + f"\n\nDecision: {updated.status if updated else status}"
        )

    return router
