from __future__ import annotations

import asyncio


class UiPreferencesService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def get_mode(self, telegram_user_id: int) -> str:
        if not self.redis_client:
            return "SIMPLE"
        payload = await asyncio.to_thread(self.redis_client.get, self._key(telegram_user_id))
        if not payload:
            return "SIMPLE"
        return str(payload).upper()

    async def set_mode(self, telegram_user_id: int, mode: str) -> str:
        normalized = mode.upper() if mode else "SIMPLE"
        if normalized not in {"SIMPLE", "PRO"}:
            normalized = "SIMPLE"
        if self.redis_client:
            await asyncio.to_thread(self.redis_client.setex, self._key(telegram_user_id), 86400 * 30, normalized)
        return normalized

    async def toggle_mode(self, telegram_user_id: int) -> str:
        current = await self.get_mode(telegram_user_id)
        target = "PRO" if current == "SIMPLE" else "SIMPLE"
        return await self.set_mode(telegram_user_id, target)

    @staticmethod
    def _key(telegram_user_id: int) -> str:
        return f"em:ui_mode:{telegram_user_id}"
