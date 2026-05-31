from datetime import datetime
import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, Message

from app.db.redis_client import build_redis_client
from app.repositories.ai_memory import AIMemoryRepository
from app.services.ai_agent import AIAssistantAgent
from app.services.facebook_promo_ai import (
    FacebookPromoAIService,
    FacebookGraphRequest,
)

if TYPE_CHECKING:
    from app.core.runtime import AppContext

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous Social Media Manager for a user's Facebook Page and Telegram channels/groups.
You help the user create, schedule, and publish promotional content to their selected destinations.

RESPONSE FORMAT RULES (STRICTLY FOLLOW):
- Use ONLY plain text with emojis. Do NOT use any Markdown or HTML tags.
- Start each bullet point with a relevant emoji (✅ 📌 🎯 📝 🚀 💡 ⚡ 🔥 📊 🎨 💬 📅).
- Keep each bullet point SHORT (under 15 words).
- Maximum 5 bullet points per response.
- Put an empty line between each section or paragraph.
- Keep total response under 100 words unless the user asks for detail.
- Be warm, friendly, enthusiastic, and human-like.
- If the user speaks Bengali/Banglish, reply in the same language.

FUNCTIONAL RULES:
- You are fully authorized and encouraged to include direct links (e.g. Telegram channel links, website URLs) in your generated posts. Sharing links is fully supported.
- When the user wants to publish or schedule a post, you MUST first call the list_targets tool if you do not already know the available destinations.
- Identify the user's intended destination from their request (e.g., matching a channel/group name they mention).
- If the user asks about channels/groups specifically (e.g., "কোন কোন চ্যানেলে পোস্ট করতে পারি?", "আমার চ্যানেল কোনগুলো?"), call list_targets and show ONLY the "display_telegram_only" field from the result. Do NOT show Facebook Page unless the user explicitly asks about Facebook or asks about ALL destinations.
- If the user asks about all destinations or where they can post in general, show the "display_all" field from the result.
- CRITICAL: When displaying targets, copy the "display_telegram_only" or "display_all" text EXACTLY as returned. NEVER invent names, NEVER use generic labels like "Telegram Channel 1" or "Channel 2", NEVER add @usernames that are not in the data. Show the real names only.
- If the target is ambiguous or not specified, list the available targets and ask the user to clarify where they want to publish/schedule.
- If enough details are given or the user confirms/approves a draft (e.g., says "Ok", "পোস্ট করো", "Confirm", "Publish"), you MUST call the publish_post tool immediately with the correct target_id.
- For scheduled posts, call the schedule_future_post tool with the correct target_id.
- For permanent rules/preferences, use save_user_preference tool.
- Always follow saved user preferences.

CRITICAL RULE (MUST OBEY):
- You must NEVER just tell the user that a post has been published or scheduled without ACTUALLY invoking the corresponding tool (publish_post or schedule_future_post)!
- Saying "Post publish hoye geche" or similar without calling the tool is a system failure. You MUST call the tool first, receive the success response from the system, and only then tell the user that the post is live.
"""


def register_facebook_promo_chat(app_context: "AppContext") -> Router:
    router = Router(name="facebook_promo_chat")

    redis_client = build_redis_client(app_context.settings)
    gemini_key = app_context.settings.gemini_api_key
    agent = AIAssistantAgent(api_key=gemini_key, model=app_context.settings.gemini_text_model)
    memory_repo = AIMemoryRepository(app_context.oracle_client)

    async def _redis_get(key: str) -> bytes | None:
        if not redis_client:
            return None
        return await asyncio.to_thread(redis_client.get, key)

    async def _redis_setex(key: str, ttl: int, value: str) -> None:
        if not redis_client:
            return
        await asyncio.to_thread(redis_client.setex, key, ttl, value)

    async def _redis_delete(key: str) -> None:
        if not redis_client:
            return
        await asyncio.to_thread(redis_client.delete, key)

    async def _get_chat_history(user_id: int) -> list[dict]:
        data = await _redis_get(f"fbpromo_chat_hist:{user_id}")
        return json.loads(data) if data else []

    async def _save_chat_history(user_id: int, history: list[dict]) -> None:
        await _redis_setex(
            f"fbpromo_chat_hist:{user_id}",
            86400,
            json.dumps(history[-40:]),
        )

    @router.callback_query(F.data == "fbpromo:startchat")
    async def start_chat_mode(callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        await _redis_setex(f"fbpromo_chat_mode:{user_id}", 3600, "1")
        await _redis_delete(f"fbpromo_chat_media:{user_id}")
        await _redis_delete(f"fbpromo_chat_hist:{user_id}")  # Reset history to clear any hallucinated refusal loop!
        await callback.answer()
        await callback.message.answer(
            "💬 <b>Facebook Promo AI Assistant</b>\n\n"
            "🤖 আমি আপনার AI সোশ্যাল মিডিয়া ম্যানেজার!\n"
            "আমাকে স্বাভাবিকভাবে কথা বলুন।\n\n"
            "🎯 উদাহরণ: 'আমাদের সামার সেল নিয়ে একটা পোস্ট বানাও'\n\n"
            "❌ বের হতে চাইলে টাইপ করুন /exit",
            parse_mode=ParseMode.HTML,
        )

    @router.message(F.text == "/exit")
    async def exit_chat_mode(message: Message) -> None:
        user_id = message.from_user.id
        await _redis_delete(f"fbpromo_chat_mode:{user_id}")
        await _redis_delete(f"fbpromo_chat_hist:{user_id}")  # Reset history on exit
        await message.answer("Exited AI Chat Mode. You can navigate the menu normally now.")

    async def is_in_chat_mode(message: Message) -> bool:
        user_id = message.from_user.id
        in_chat = await _redis_get(f"fbpromo_chat_mode:{user_id}")
        return bool(in_chat)

    @router.message(is_in_chat_mode)
    async def handle_chat_message(message: Message) -> None:
        user_id = message.from_user.id
        
        # Check if user sent /exit explicitly
        if message.text == "/exit":
            await exit_chat_mode(message)
            return

        # Store media if a photo is sent
        if message.photo:
            try:
                from app.services.media_utils import store_message_media
                media_path, media_name, content_type = await store_message_media(message.bot, message)
                media_info = {
                    "path": media_path,
                    "name": media_name,
                    "type": content_type
                }
                await _redis_setex(f"fbpromo_chat_media:{user_id}", 3600, json.dumps(media_info))
            except Exception as e:
                logger.error("Failed to store uploaded photo: %s", e)

        # Retrieve user text / caption
        raw_user_text = message.text or message.caption or ""
        
        # Prepare context-aware user prompt for the AI agent
        if message.photo:
            if raw_user_text:
                user_text = f"[User uploaded a photo. It has been successfully saved to our system and will be automatically attached if you publish or schedule this post.]\nUser caption/instruction: {raw_user_text}"
            else:
                user_text = "[User uploaded a photo without any caption. Ask them what they want to do with this photo, or write a draft caption/post text for it.]"
        else:
            user_text = raw_user_text

        fb_service = FacebookPromoAIService(
            redis_client=redis_client,
            graph_api_enabled=app_context.settings.facebook_promo_graph_api_enabled,
            alibaba_image_api_enabled=False,
            alibaba_api_key=app_context.settings.alibaba_api_key,
        )

        # --- Tool implementations ---

        async def list_targets() -> dict:
            """Returns structured target data with a pre-formatted display string."""
            profile = await fb_service.get_profile(user_id)
            targets = []
            if profile.page_id:
                targets.append({
                    "id": "facebook",
                    "name": "Facebook Page",
                    "type": "facebook"
                })

            def _get_db_user_id(tg_id):
                with app_context.oracle_client.connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_id", {"tg_id": tg_id})
                        row = cur.fetchone()
                        return row[0] if row else None

            try:
                db_user_id = await asyncio.to_thread(_get_db_user_id, user_id)
            except Exception:
                logger.exception("Failed to query DB user ID in list_targets")
                db_user_id = None

            if db_user_id is not None:
                def _get_telegram_targets(db_uid):
                    tgs = []
                    with app_context.oracle_client.connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT CHAT_IDENTIFIER, TITLE FROM EM_CHANNELS WHERE ADDED_BY_USER_ID = :db_uid AND STATUS = 'ACTIVE'",
                                {"db_uid": db_uid}
                            )
                            for row in cur.fetchall():
                                tgs.append({
                                    "id": str(row[0]),
                                    "name": row[1] or str(row[0]),
                                    "type": "telegram_channel"
                                })
                            cur.execute(
                                "SELECT CHAT_IDENTIFIER, TITLE FROM EM_GROUPS WHERE ADDED_BY_USER_ID = :db_uid AND STATUS = 'ACTIVE'",
                                {"db_uid": db_uid}
                            )
                            for row in cur.fetchall():
                                tgs.append({
                                    "id": str(row[0]),
                                    "name": row[1] or str(row[0]),
                                    "type": "telegram_group"
                                })
                    return tgs
                
                try:
                    tg_targets = await asyncio.to_thread(_get_telegram_targets, db_user_id)
                    targets.extend(tg_targets)
                except Exception:
                    logger.exception("Failed to query Telegram targets in list_targets")

            # Build pre-formatted display lines for the AI to use directly
            telegram_lines = []
            all_lines = []
            for t in targets:
                if t["type"] == "facebook":
                    all_lines.append(f"✅ {t['name']} (Facebook)")
                elif t["type"] == "telegram_channel":
                    line = f"✅ {t['name']} (টেলিগ্রাম চ্যানেল)"
                    telegram_lines.append(line)
                    all_lines.append(line)
                elif t["type"] == "telegram_group":
                    line = f"✅ {t['name']} (টেলিগ্রাম গ্রুপ)"
                    telegram_lines.append(line)
                    all_lines.append(line)

            return {
                "targets": targets,
                "display_all": "\n".join(all_lines) if all_lines else "কোনো ডেস্টিনেশন পাওয়া যায়নি।",
                "display_telegram_only": "\n".join(telegram_lines) if telegram_lines else "কোনো টেলিগ্রাম চ্যানেল/গ্রুপ কানেক্ট করা নেই।",
                "instruction": "IMPORTANT: Show the display text EXACTLY as provided above. Do NOT rename or reformat the target names."
            }

        async def publish_post(text: str, target_id: str = "facebook", include_ai_image: bool = False, image_prompt: str = "") -> str:
            await memory_repo.log_action(user_id, "PUBLISH_START", f"Target: {target_id}, Text: {text}")
            
            stored_media_json = await _redis_get(f"fbpromo_chat_media:{user_id}")
            media_path = None
            media_type = None
            if stored_media_json:
                try:
                    media_data = json.loads(stored_media_json)
                    media_path = media_data.get("path")
                    media_type = media_data.get("type")
                except Exception as e:
                    logger.error("Failed to load stored media: %s", e)

            from pathlib import Path
            
            # --- TELEGRAM PUBLISHING ---
            if target_id != "facebook" and target_id:
                try:
                    chat_id = int(target_id)
                except ValueError:
                    chat_id = target_id
                
                try:
                    if media_path:
                        if not Path(media_path).exists():
                            return f"Failed to publish to Telegram: Local media file {media_path} not found on server."
                        
                        from aiogram.types import FSInputFile
                        media_file = FSInputFile(media_path, filename=Path(media_path).name)
                        media_type_lower = (media_type or "").lower()
                        if media_type_lower.startswith("video/"):
                            await message.bot.send_video(chat_id=chat_id, video=media_file, caption=text)
                        elif media_type_lower.startswith("audio/"):
                            await message.bot.send_audio(chat_id=chat_id, audio=media_file, caption=text)
                        elif media_type_lower.startswith("application/") or media_type_lower.startswith("text/"):
                            await message.bot.send_document(chat_id=chat_id, document=media_file, caption=text)
                        else:
                            await message.bot.send_photo(chat_id=chat_id, photo=media_file, caption=text)
                    else:
                        await message.bot.send_message(chat_id=chat_id, text=text)
                    
                    if media_path:
                        await _redis_delete(f"fbpromo_chat_media:{user_id}")
                    await memory_repo.log_action(user_id, "PUBLISH_SUCCESS", f"Published to Telegram target {target_id}")
                    return f"Successfully published post to Telegram destination ({target_id})!"
                except Exception as exc:
                    err = f"Telegram Send Error: {exc}"
                    await memory_repo.log_action(user_id, "PUBLISH_ERROR", err)
                    return err

            # --- FACEBOOK PUBLISHING ---
            profile = await fb_service.get_profile(user_id)
            if not profile.page_id or not profile.page_access_token:
                return "Failed to publish: You must configure your Facebook Page ID and Access Token in the main menu first."

            if not media_path:
                url = f"https://graph.facebook.com/v24.0/{profile.page_id}/feed"
                payload = {"message": text}

                req = FacebookGraphRequest(method="POST", url=url, headers={}, payload=payload)
                resp = await fb_service.graph_adapter.execute(req, profile.page_access_token)

                if resp.ok:
                    await memory_repo.log_action(user_id, "PUBLISH_SUCCESS", f"Published OK")
                    return "Successfully published to Facebook!"
                else:
                    err = f"Facebook Graph API Error: {resp.message} {resp.body}"
                    await memory_repo.log_action(user_id, "PUBLISH_ERROR", err)
                    return err
            else:
                if not Path(media_path).exists():
                    return f"Failed to publish: Local media file {media_path} not found on server."

                # Perform multipart photo upload to Facebook Graph API
                def _upload_photo_multipart():
                    import uuid
                    from urllib import request as urllib_request, error as urllib_error
                    boundary = f"Boundary-{uuid.uuid4().hex}"
                    headers = {
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "Authorization": f"Bearer {profile.page_access_token}"
                    }

                    parts = []
                    parts.append(f"--{boundary}\r\n".encode("utf-8"))
                    parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n'.encode("utf-8"))
                    parts.append(f"{text}\r\n".encode("utf-8"))

                    filename = Path(media_path).name
                    parts.append(f"--{boundary}\r\n".encode("utf-8"))
                    parts.append(f'Content-Disposition: form-data; name="source"; filename="{filename}"\r\n'.encode("utf-8"))
                    parts.append(f"Content-Type: {media_type or 'image/jpeg'}\r\n\r\n".encode("utf-8"))

                    with open(media_path, "rb") as f:
                        parts.append(f.read())
                    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

                    body = b"".join(parts)
                    url = f"https://graph.facebook.com/v24.0/{profile.page_id}/photos"

                    req = urllib_request.Request(url, data=body, headers=headers, method="POST")
                    try:
                        with urllib_request.urlopen(req, timeout=30.0) as response:
                            res_body = response.read(2000).decode("utf-8", errors="replace")
                            return True, res_body
                    except urllib_error.HTTPError as exc:
                        err_body = exc.read(2000).decode("utf-8", errors="replace")
                        return False, f"HTTP Error {exc.code}: {err_body}"
                    except Exception as exc:
                        return False, str(exc)

                ok, result_str = await asyncio.to_thread(_upload_photo_multipart)
                if ok:
                    await _redis_delete(f"fbpromo_chat_media:{user_id}")
                    await memory_repo.log_action(user_id, "PUBLISH_SUCCESS", f"Published Photo OK")
                    return "Successfully published photo post to Facebook!"
                else:
                    err = f"Facebook Graph API Photo Error: {result_str}"
                    await memory_repo.log_action(user_id, "PUBLISH_ERROR", err)
                    return err

        async def schedule_future_post(text: str, datetime_str: str, target_id: str = "facebook", include_ai_image: bool = False, image_prompt: str = "") -> str:
            await memory_repo.log_action(user_id, "SCHEDULE_START", f"Target: {target_id}, Time: {datetime_str}, Text: {text}")
            profile = await fb_service.get_profile(user_id)

            if target_id == "facebook" or not target_id:
                if not profile.page_id:
                    return "Failed to schedule: No Facebook Page configured."
                channel_ident = str(profile.page_id)
                channel_title = "Facebook Page"
            else:
                channel_ident = target_id
                def _lookup_title(chat_ident):
                    with app_context.oracle_client.connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT TITLE FROM EM_CHANNELS WHERE CHAT_IDENTIFIER = :ci", {"ci": chat_ident})
                            row = cur.fetchone()
                            if row:
                                return row[0]
                            cur.execute("SELECT TITLE FROM EM_GROUPS WHERE CHAT_IDENTIFIER = :ci", {"ci": chat_ident})
                            row = cur.fetchone()
                            if row:
                                return row[0]
                            return chat_ident
                try:
                    channel_title = await asyncio.to_thread(_lookup_title, target_id)
                except Exception:
                    logger.exception("Failed to lookup channel/group title")
                    channel_title = target_id

            try:
                datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return "Failed: Invalid datetime_str format. Must be YYYY-MM-DD HH:MM:SS"

            stored_media_json = await _redis_get(f"fbpromo_chat_media:{user_id}")
            media_path = None
            media_type = None
            if stored_media_json:
                try:
                    media_data = json.loads(stored_media_json)
                    media_path = media_data.get("path")
                    media_type = media_data.get("type")
                except Exception as e:
                    logger.error("Failed to load stored media: %s", e)

            sql = (
                "INSERT INTO EM_SCHEDULED_POSTS "
                "(CHANNEL_IDENTIFIER, CHANNEL_TITLE, MESSAGE_TEXT, "
                "SCHEDULED_FOR, MEDIA_PATH, MEDIA_TYPE, STATUS, CREATED_BY_USER_ID) "
                "VALUES ("
                ":channel_ident, :channel_title, :text, "
                "TO_TIMESTAMP(:dt_str, 'YYYY-MM-DD HH24:MI:SS'), "
                ":media, :mtype, 'PENDING', "
                "(SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_user))"
            )
            params = {
                "channel_ident": channel_ident,
                "channel_title": channel_title,
                "text": text,
                "dt_str": datetime_str,
                "media": media_path,
                "mtype": media_type,
                "tg_user": user_id,
            }
            
            def _do_schedule():
                with app_context.oracle_client.connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                    conn.commit()

            try:
                await asyncio.to_thread(_do_schedule)
                if media_path:
                    await _redis_delete(f"fbpromo_chat_media:{user_id}")
                return f"Successfully scheduled post for {datetime_str} to {channel_title}."
            except Exception as e:
                logger.error("Schedule DB error: %s", e)
                return "Failed to save schedule in the database."

        async def save_user_preference(key: str, value: str) -> str:
            success = await memory_repo.save_preference(user_id, key, value)
            return "Preference saved successfully." if success else "Failed to save preference."

        async def forget_user_preference(key: str) -> str:
            success = await memory_repo.forget_preference(user_id, key)
            return "Preference removed successfully." if success else "Failed to remove preference."

        callbacks = {
            "list_targets": list_targets,
            "publish_post": publish_post,
            "schedule_future_post": schedule_future_post,
            "save_user_preference": save_user_preference,
            "forget_user_preference": forget_user_preference,
        }

        # Inject preferences into prompt
        prefs = await memory_repo.get_all_preferences(user_id)
        pref_lines = [f"- {k}: {v}" for k, v in prefs.items()]
        dynamic_prompt = SYSTEM_PROMPT
        if prefs:
            dynamic_prompt += "\n\nUSER SAVED PREFERENCES (Follow these strictly):\n" + "\n".join(pref_lines)

        history = await _get_chat_history(user_id)

        try:
            await message.chat.do("typing")
        except Exception:
            pass

        try:
            result = await agent.chat(dynamic_prompt, history, user_text, callbacks)
            reply = result.text or "I processed your request but have no text to show."
        except Exception as e:
            logger.error("AI Agent error: %s", e, exc_info=True)
            reply = f"Sorry, I encountered an error: {e}"

        # Strip any markdown/html the AI might have added
        reply = re.sub(r'[*_`#]', '', reply)

        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": reply}]})
        await _save_chat_history(user_id, history)

        await message.answer(reply)

    return router
