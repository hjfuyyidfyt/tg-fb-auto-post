from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass


REQUESTABLE_ROLE_KEYS = {"VIEWER", "CHANNEL_MANAGER", "GROUP_MANAGER", "MODERATOR"}


@dataclass(slots=True)
class AccessRequest:
    telegram_user_id: int
    username: str | None
    display_name: str | None
    role_key: str
    status: str = "PENDING"


class AccessRequestService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def create_request(
        self,
        telegram_user_id: int,
        username: str | None,
        display_name: str | None,
        role_key: str,
    ) -> AccessRequest:
        request = AccessRequest(
            telegram_user_id=telegram_user_id,
            username=username,
            display_name=display_name,
            role_key=role_key,
        )
        await self._set_request(request)
        return request

    async def get_request(self, telegram_user_id: int) -> AccessRequest | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._request_key(telegram_user_id))
        if not payload:
            return None
        return AccessRequest(**json.loads(payload))

    async def update_status(self, telegram_user_id: int, status: str) -> AccessRequest | None:
        request = await self.get_request(telegram_user_id)
        if not request:
            return None
        request.status = status
        await self._set_request(request)
        return request

    async def list_pending(self) -> list[AccessRequest]:
        if not self.redis_client:
            return []
        keys = await asyncio.to_thread(self.redis_client.keys, "em:access_request:*")
        if not keys:
            return []
        results: list[AccessRequest] = []
        for key in keys:
            payload = await asyncio.to_thread(self.redis_client.get, key)
            if not payload:
                continue
            request = AccessRequest(**json.loads(payload))
            if request.status == "PENDING":
                results.append(request)
        results.sort(key=lambda item: item.telegram_user_id)
        return results

    async def _set_request(self, request: AccessRequest) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._request_key(request.telegram_user_id),
            60 * 60 * 24 * 7,
            json.dumps(asdict(request)),
        )

    @staticmethod
    def _request_key(telegram_user_id: int) -> str:
        return f"em:access_request:{telegram_user_id}"
