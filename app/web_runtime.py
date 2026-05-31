from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aiogram import Bot
from aiogram.types import BufferedInputFile
from fastapi import Request, UploadFile
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from app.web_safe_helpers import build_dashboard_redirect_url, reauth_redirect_target, safe_next_url


def read_session_payload(request: Request) -> dict | None:
    serializer: URLSafeSerializer = request.app.state.serializer
    payload = request.cookies.get("em_session")
    if not payload:
        return None
    try:
        data = serializer.loads(payload)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data


def read_session_user_id(request: Request) -> int | None:
    data = read_session_payload(request)
    if not data:
        return None
    try:
        return int(data["telegram_user_id"])
    except Exception:
        return None


def read_sensitive_payload(request: Request) -> dict | None:
    serializer: URLSafeSerializer = request.app.state.serializer
    payload = request.cookies.get("em_sensitive")
    if not payload:
        return None
    try:
        data = serializer.loads(payload)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data

def read_csrf_token(request: Request) -> str:
    data = read_session_payload(request) or {}
    token = data.get("csrf_token")
    return token if isinstance(token, str) else ""


def validate_csrf(request: Request, submitted_token: str) -> bool:
    expected_token = read_csrf_token(request)
    if not expected_token or not submitted_token:
        return False
    return secrets.compare_digest(expected_token, submitted_token)


def has_sensitive_session(request: Request) -> bool:
    user_id = read_session_user_id(request)
    payload = read_sensitive_payload(request)
    if user_id is None or not payload:
        return False
    try:
        payload_user_id = int(payload["telegram_user_id"])
        expires_at = datetime.fromisoformat(payload["expires_at"])
    except Exception:
        return False
    if payload_user_id != user_id:
        return False
    return expires_at >= datetime.now(timezone.utc)


def reauth_redirect_url(query: str = "", status_filter: str = "ALL") -> str:
    return reauth_redirect_target(query, status_filter)


def dashboard_redirect(
    notice: str | None = None,
    error: str | None = None,
    query: str = "",
    status_filter: str = "ALL",
) -> RedirectResponse:
    url = build_dashboard_redirect_url(
        notice=notice,
        error=error,
        query=query,
        status_filter=status_filter,
    )
    return RedirectResponse(url=url, status_code=302)


async def validate_upload(media_file: UploadFile, max_bytes: int) -> str | None:
    payload = await media_file.read()
    await media_file.seek(0)
    if len(payload) > max_bytes:
        return f"Uploaded file is too large. Max supported size is {max_bytes // (1024 * 1024)} MB."
    return None


async def store_schedule_media(media_file: UploadFile, schedule_media_dir: Path) -> tuple[str, str, str]:
    schedule_media_dir.mkdir(parents=True, exist_ok=True)
    payload = await media_file.read()
    await media_file.seek(0)
    media_name = media_file.filename or "upload.bin"
    safe_name = f"{uuid4().hex}_{media_name.replace(' ', '_')}"
    target_path = schedule_media_dir / safe_name
    await asyncio.to_thread(target_path.write_bytes, payload)
    return str(target_path), media_name, (media_file.content_type or "")


async def send_web_content(
    bot_api: Bot,
    chat_identifier: str,
    message_text: str,
    media_file: UploadFile | None,
) -> None:
    if not media_file:
        await bot_api.send_message(chat_identifier, message_text)
        return

    payload = await media_file.read()
    await media_file.seek(0)
    media_name = media_file.filename or "upload.bin"
    file = BufferedInputFile(payload, filename=media_name)
    content_type = media_file.content_type or ""
    caption = message_text or None

    if content_type.startswith("image/"):
        await bot_api.send_photo(chat_identifier, photo=file, caption=caption)
        return
    if content_type.startswith("video/"):
        await bot_api.send_video(chat_identifier, video=file, caption=caption)
        return

    await bot_api.send_document(chat_identifier, document=file, caption=caption)
