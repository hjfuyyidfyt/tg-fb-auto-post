from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field


DEFAULT_BAD_WORDS = [
    "fuck",
    "shit",
    "bitch",
    "madarchod",
    "bokachoda",
    "harami",
]


@dataclass(slots=True)
class GroupFilterState:
    anti_link_enabled: bool = False
    bad_word_enabled: bool = False
    custom_bad_words: list[str] = field(default_factory=list)

    @property
    def effective_bad_words(self) -> set[str]:
        return {word.lower() for word in [*DEFAULT_BAD_WORDS, *self.custom_bad_words] if word.strip()}


class GroupFilterService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def get_state(self, group_key: str) -> GroupFilterState:
        if not self.redis_client:
            return GroupFilterState()
        payload = await asyncio.to_thread(self.redis_client.get, self._group_key(group_key))
        if not payload:
            return GroupFilterState()
        data = json.loads(payload)
        return GroupFilterState(
            anti_link_enabled=bool(data.get("anti_link_enabled", False)),
            bad_word_enabled=bool(data.get("bad_word_enabled", False)),
            custom_bad_words=list(data.get("custom_bad_words", [])),
        )

    async def toggle_anti_link(self, group_key: str) -> GroupFilterState:
        state = await self.get_state(group_key)
        state.anti_link_enabled = not state.anti_link_enabled
        await self._set_state(group_key, state)
        return state

    async def toggle_bad_word(self, group_key: str) -> GroupFilterState:
        state = await self.get_state(group_key)
        state.bad_word_enabled = not state.bad_word_enabled
        await self._set_state(group_key, state)
        return state

    async def add_bad_word(self, group_key: str, word: str) -> GroupFilterState:
        state = await self.get_state(group_key)
        normalized = word.strip().lower()
        if normalized and normalized not in {item.lower() for item in state.custom_bad_words}:
            state.custom_bad_words.append(normalized)
            state.custom_bad_words.sort()
            await self._set_state(group_key, state)
        return state

    async def remove_bad_word(self, group_key: str, word: str) -> GroupFilterState:
        state = await self.get_state(group_key)
        normalized = word.strip().lower()
        state.custom_bad_words = [item for item in state.custom_bad_words if item.lower() != normalized]
        await self._set_state(group_key, state)
        return state

    async def clear_custom_bad_words(self, group_key: str) -> GroupFilterState:
        state = await self.get_state(group_key)
        state.custom_bad_words = []
        await self._set_state(group_key, state)
        return state

    @staticmethod
    def contains_link(text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in ("http://", "https://", "t.me/", "telegram.me/", "www."))

    @staticmethod
    def contains_bad_word(text: str, words: set[str]) -> str | None:
        lowered = text.lower()
        for word in words:
            if word and word in lowered:
                return word
        return None

    async def _set_state(self, group_key: str, state: GroupFilterState) -> None:
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
        return f"em:filters:{group_key}"
