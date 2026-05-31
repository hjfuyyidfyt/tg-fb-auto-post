from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass


@dataclass(slots=True)
class WarningEntry:
    user_id: int
    label: str
    count: int


class WarningService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def increment_warning(self, group_key: str, user_id: int, label: str) -> int:
        state = await self._get_group_state(group_key)
        entry = state.get(str(user_id), {"label": label, "count": 0})
        entry["label"] = label
        entry["count"] = int(entry.get("count", 0)) + 1
        state[str(user_id)] = entry
        await self._set_group_state(group_key, state)
        return entry["count"]

    async def decrement_warning(self, group_key: str, user_id: int, label: str) -> int:
        state = await self._get_group_state(group_key)
        entry = state.get(str(user_id), {"label": label, "count": 0})
        current = max(int(entry.get("count", 0)) - 1, 0)
        if current == 0:
            state.pop(str(user_id), None)
        else:
            entry["label"] = label
            entry["count"] = current
            state[str(user_id)] = entry
        await self._set_group_state(group_key, state)
        return current

    async def get_warning_count(self, group_key: str, user_id: int) -> int:
        state = await self._get_group_state(group_key)
        return int(state.get(str(user_id), {}).get("count", 0))

    async def get_top_warnings(self, group_key: str, limit: int = 10) -> list[WarningEntry]:
        state = await self._get_group_state(group_key)
        items = [
            WarningEntry(
                user_id=int(raw_user_id),
                label=str(entry.get("label") or raw_user_id),
                count=int(entry.get("count", 0)),
            )
            for raw_user_id, entry in state.items()
            if int(entry.get("count", 0)) > 0
        ]
        items.sort(key=lambda item: (-item.count, item.label.lower()))
        return items[:limit]

    async def clear_group_warnings(self, group_key: str) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._group_key(group_key))

    async def _get_group_state(self, group_key: str) -> dict[str, dict[str, object]]:
        if not self.redis_client:
            return {}
        payload = await asyncio.to_thread(self.redis_client.get, self._group_key(group_key))
        if not payload:
            return {}
        return json.loads(payload)

    async def _set_group_state(self, group_key: str, state: dict[str, dict[str, object]]) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._group_key(group_key),
            60 * 60 * 24 * 30,
            json.dumps(state),
        )

    @staticmethod
    def _group_key(group_key: str) -> str:
        return f"em:warnings:{group_key}"
