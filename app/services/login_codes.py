from __future__ import annotations

import asyncio
import secrets


class LoginCodeService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def issue_code(self, telegram_user_id: int, ttl_seconds: int = 600) -> str:
        if not self.redis_client:
            return "000000"
        code = f"{secrets.randbelow(1_000_000):06d}"
        await asyncio.to_thread(
            self.redis_client.setex,
            self._code_key(telegram_user_id),
            ttl_seconds,
            code,
        )
        return code

    async def validate_code(self, telegram_user_id: int, code: str) -> bool:
        if not self.redis_client:
            return False
        stored = await asyncio.to_thread(self.redis_client.get, self._code_key(telegram_user_id))
        if not stored:
            return False
        stored_value = stored.decode() if isinstance(stored, bytes) else str(stored)
        if secrets.compare_digest(stored_value, code.strip()):
            await asyncio.to_thread(self.redis_client.delete, self._code_key(telegram_user_id))
            return True
        return False

    @staticmethod
    def _code_key(telegram_user_id: int) -> str:
        return f"em:login_code:{telegram_user_id}"
