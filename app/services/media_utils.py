from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.types import Message


MEDIA_ONLY_SENTINEL = "[media-only]"
BOT_SCHEDULE_MEDIA_DIR = Path("/app/data/scheduled_media")


def message_has_supported_media(message: Message) -> bool:
    return bool(message.photo or message.video or message.document)


def extract_message_text(message: Message) -> str:
    return ((message.caption or message.text or "")).strip()


def describe_incoming_media(message: Message) -> str:
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        return "document"
    if message.audio:
        return "audio"
    if message.voice:
        return "voice"
    if message.video_note:
        return "video note"
    if message.animation:
        return "animation"
    if message.sticker:
        return "sticker"
    return "media"


async def send_message_content(bot: Bot, chat_identifier: str, message: Message):
    text = extract_message_text(message)
    if message.photo:
        return await bot.send_photo(
            chat_identifier,
            photo=message.photo[-1].file_id,
            caption=text or None,
        )
    if message.video:
        return await bot.send_video(
            chat_identifier,
            video=message.video.file_id,
            caption=text or None,
        )
    if message.document:
        return await bot.send_document(
            chat_identifier,
            document=message.document.file_id,
            caption=text or None,
        )
    return await bot.send_message(chat_identifier, text)


async def send_stored_content(
    bot: Bot,
    chat_identifier: str,
    message_text: str | None,
    media_path: str | None = None,
    media_name: str | None = None,
    media_type: str | None = None,
):
    text = (message_text or "").strip()
    if not media_path:
        return await bot.send_message(chat_identifier, text)

    media_file = FSInputFile(media_path, filename=media_name or Path(media_path).name)
    caption = None if text == MEDIA_ONLY_SENTINEL else (text or None)
    content_type = (media_type or "").lower()
    if content_type.startswith("image/"):
        return await bot.send_photo(chat_identifier, photo=media_file, caption=caption)
    if content_type.startswith("video/"):
        return await bot.send_video(chat_identifier, video=media_file, caption=caption)
    return await bot.send_document(chat_identifier, document=media_file, caption=caption)


async def store_message_media(
    bot: Bot,
    message: Message,
    target_dir: Path = BOT_SCHEDULE_MEDIA_DIR,
) -> tuple[str, str, str]:
    if not message_has_supported_media(message):
        raise ValueError("Message does not contain supported media.")

    target_dir.mkdir(parents=True, exist_ok=True)
    if message.photo:
        file_id = message.photo[-1].file_id
        original_name = f"{file_id}.jpg"
        content_type = "image/jpeg"
    elif message.video:
        file_id = message.video.file_id
        original_name = message.video.file_name or f"{file_id}.mp4"
        content_type = message.video.mime_type or "video/mp4"
    else:
        file_id = message.document.file_id
        original_name = message.document.file_name or "upload.bin"
        content_type = message.document.mime_type or ""

    safe_name = f"{uuid4().hex}_{original_name.replace(' ', '_')}"
    target_path = target_dir / safe_name
    telegram_file = await bot.get_file(file_id)
    with target_path.open("wb") as output:
        await bot.download(telegram_file, destination=output)
    return str(target_path), original_name, content_type


async def write_bytes(path: Path, payload: bytes) -> None:
    await asyncio.to_thread(path.write_bytes, payload)
