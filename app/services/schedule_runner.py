from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

from app.core.runtime import AppContext
from app.db.redis_client import build_redis_client
from app.models.audit import AuditLogRecord
from app.repositories.audit import AuditRepository
from app.services.schedule import ScheduleService

logger = logging.getLogger(__name__)
MEDIA_ONLY_SENTINEL = "[media-only]"


class ScheduleRunner:
    def __init__(self, app_context: AppContext, bot: Bot, poll_interval_seconds: int = 20) -> None:
        self.app_context = app_context
        self.bot = bot
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        redis_client = build_redis_client(app_context.settings)
        self.schedule_service = ScheduleService(app_context, redis_client=redis_client)

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._run_loop(), name="schedule-runner")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None

    async def _run_loop(self) -> None:
        await asyncio.sleep(15)
        while not self._stop_event.is_set():
            try:
                await self._process_due_posts()
            except Exception:
                logger.exception("Schedule runner loop failed")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _process_due_posts(self) -> None:
        due_posts = await self.schedule_service.list_due_pending()
        for post in due_posts:
            try:
                await self._send_scheduled_content(post)
                next_run = self.schedule_service.next_occurrence(post)
                if next_run:
                    await self.schedule_service.reschedule_post(post.id, next_run)
                    await self._record_event(
                        "RECURRING_SCHEDULE_SENT",
                        post,
                        details=f"next={next_run}",
                    )
                    logger.info(
                        "Recurring scheduled post sent to %s and rescheduled for %s",
                        post.channel_identifier,
                        next_run,
                    )
                else:
                    await self.schedule_service.update_status(post.id, "SENT")
                    await self._record_event("SCHEDULE_SENT", post)
                    logger.info("Scheduled post sent to %s", post.channel_identifier)
            except TelegramBadRequest as exc:
                logger.warning(
                    "Scheduled post failed for %s: %s",
                    post.channel_identifier,
                    exc.message,
                )
                await self.schedule_service.update_status(post.id, "FAILED")
                await self._record_event("SCHEDULE_FAILED", post, details=exc.message)
            except FileNotFoundError as exc:
                logger.warning("Scheduled media file missing for %s: %s", post.channel_identifier, exc)
                await self.schedule_service.update_status(post.id, "FAILED")
                await self._record_event("SCHEDULE_MEDIA_MISSING", post, details=str(exc))
            except Exception as exc:
                logger.exception("Unexpected schedule send failure for %s", post.channel_identifier)
                await self.schedule_service.update_status(post.id, "FAILED")
                await self._record_event("SCHEDULE_FAILED", post, details=str(exc)[:200])

    async def _send_scheduled_content(self, post) -> None:
        if post.channel_title == 'Facebook Page':
            await self._publish_to_facebook(post)
            return

        if not post.media_path:
            await self.bot.send_message(post.channel_identifier, post.message_text)
            return

        if not Path(post.media_path).exists():
            raise FileNotFoundError(post.media_path)
        media_file = FSInputFile(post.media_path, filename=post.media_name or Path(post.media_path).name)
        caption = None if post.message_text == MEDIA_ONLY_SENTINEL else (post.message_text or None)
        media_type = (post.media_type or "").lower()
        if media_type.startswith("image/"):
            await self.bot.send_photo(post.channel_identifier, photo=media_file, caption=caption)
            return
        if media_type.startswith("video/"):
            await self.bot.send_video(post.channel_identifier, video=media_file, caption=caption)
            return

        await self.bot.send_document(post.channel_identifier, document=media_file, caption=caption)

    async def _publish_to_facebook(self, post) -> None:
        if not post.created_by_user_id:
            raise ValueError("No user ID associated with this scheduled post.")

        # Get telegram user ID from database user ID
        def _get_tg_user(db_user_id):
            with self.app_context.oracle_client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT TELEGRAM_USER_ID FROM EM_USERS WHERE ID = :user_id", {"user_id": db_user_id})
                    row = cur.fetchone()
                    return row[0] if row else None

        tg_user_id = await asyncio.to_thread(_get_tg_user, post.created_by_user_id)
        if not tg_user_id:
            raise ValueError(f"Could not find Telegram user for DB user ID {post.created_by_user_id}")

        from app.services.facebook_promo_ai import FacebookPromoAIService, FacebookGraphRequest
        from app.db.redis_client import build_redis_client
        from urllib import request as urllib_request, error as urllib_error
        import json
        
        fb_service = FacebookPromoAIService(
            redis_client=build_redis_client(self.app_context.settings),
            graph_api_enabled=self.app_context.settings.facebook_promo_graph_api_enabled,
            alibaba_image_api_enabled=False,
        )
        
        profile = await fb_service.get_profile(tg_user_id)
        if not profile.page_id or not profile.page_access_token:
            raise ValueError("Facebook Page ID or Access Token is not configured for this user.")

        if not post.media_path:
            # Text only post
            url = f"https://graph.facebook.com/v24.0/{profile.page_id}/feed"
            payload = {"message": post.message_text}
            req = FacebookGraphRequest(method="POST", url=url, headers={}, payload=payload)
            resp = await fb_service.graph_adapter.execute(req, profile.page_access_token)
            if not resp.ok:
                raise Exception(f"Facebook API feed error: {resp.message} {resp.body}")
        else:
            # Photo post (using multipart/form-data upload)
            if not Path(post.media_path).exists():
                raise FileNotFoundError(f"Local media file not found: {post.media_path}")
            
            # Perform multipart upload in a separate thread
            def _upload_photo_multipart():
                import uuid
                boundary = f"Boundary-{uuid.uuid4().hex}"
                headers = {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Authorization": f"Bearer {profile.page_access_token}"
                }
                
                # Construct multipart body
                parts = []
                # caption part
                parts.append(f"--{boundary}\r\n".encode("utf-8"))
                parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n'.encode("utf-8"))
                parts.append(f"{post.message_text}\r\n".encode("utf-8"))
                
                # file part
                filename = post.media_name or Path(post.media_path).name
                parts.append(f"--{boundary}\r\n".encode("utf-8"))
                parts.append(f'Content-Disposition: form-data; name="source"; filename="{filename}"\r\n'.encode("utf-8"))
                parts.append(f"Content-Type: {post.media_type or 'image/jpeg'}\r\n\r\n".encode("utf-8"))
                
                with open(post.media_path, "rb") as f:
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
            if not ok:
                raise Exception(f"Facebook photo upload failed: {result_str}")

    async def _record_event(self, action_key: str, post, details: str | None = None) -> None:
        if not self.app_context.oracle_client:
            return
        try:
            await asyncio.to_thread(
                AuditRepository(self.app_context.oracle_client).insert,
                AuditLogRecord(
                    actor_user_id=None,
                    action_key=action_key,
                    target_type="SCHEDULE",
                    target_id=str(post.id or post.channel_identifier),
                    details=details or post.channel_identifier,
                ),
            )
        except Exception:
            logger.exception("Failed to write schedule audit event: %s", action_key)
