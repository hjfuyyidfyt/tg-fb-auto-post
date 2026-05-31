from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class GroupEventState:
    welcome_enabled: bool = False
    join_log_enabled: bool = False
    welcome_template: str | None = None


class GroupEventService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def get_state(self, group_key: str) -> GroupEventState:
        if not self.redis_client:
            return GroupEventState()
        payload = await asyncio.to_thread(self.redis_client.get, self._group_key(group_key))
        if not payload:
            return GroupEventState()
        data = json.loads(payload)
        return GroupEventState(
            welcome_enabled=bool(data.get("welcome_enabled", False)),
            join_log_enabled=bool(data.get("join_log_enabled", False)),
            welcome_template=data.get("welcome_template"),
        )

    async def toggle_welcome(self, group_key: str) -> GroupEventState:
        state = await self.get_state(group_key)
        state.welcome_enabled = not state.welcome_enabled
        await self._set_state(group_key, state)
        return state

    async def toggle_join_log(self, group_key: str) -> GroupEventState:
        state = await self.get_state(group_key)
        state.join_log_enabled = not state.join_log_enabled
        await self._set_state(group_key, state)
        return state

    async def set_welcome_template(self, group_key: str, template: str) -> GroupEventState:
        state = await self.get_state(group_key)
        state.welcome_template = template.strip()
        await self._set_state(group_key, state)
        return state

    async def clear_welcome_template(self, group_key: str) -> GroupEventState:
        state = await self.get_state(group_key)
        state.welcome_template = None
        await self._set_state(group_key, state)
        return state

    @staticmethod
    def render_welcome(template: str | None, member_label: str, group_label: str) -> str:
        base = template or "Welcome {member} to {group}."
        return base.replace("{member}", member_label).replace("{group}", group_label)

    async def _set_state(self, group_key: str, state: GroupEventState) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._group_key(group_key),
            60 * 60 * 24 * 30,
            json.dumps(asdict(state)),
        )

    @staticmethod
    def _group_key(group_key: str) -> str:
        return f"em:events:{group_key}"
