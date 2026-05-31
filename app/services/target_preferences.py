from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass

from app.models.entities import ManagedEntityRecord


def rank_channel_records(
    records: list[ManagedEntityRecord],
    favorite_ids: set[int],
    recent_ids: list[int],
) -> list[tuple[ManagedEntityRecord, bool, bool]]:
    recent_order = {entity_id: index for index, entity_id in enumerate(recent_ids)}

    def sort_key(record: ManagedEntityRecord) -> tuple[int, int, str]:
        return (
            0 if record.id in favorite_ids else 1,
            recent_order.get(record.id, 9999),
            (record.title or record.chat_identifier).lower(),
        )

    ranked = sorted(records, key=sort_key)
    return [
        (record, record.id in favorite_ids, record.id in recent_order)
        for record in ranked
    ]


def build_quick_pick_records(
    records: list[ManagedEntityRecord],
    favorite_ids: set[int],
    recent_ids: list[int],
    limit: int = 3,
) -> list[tuple[ManagedEntityRecord, bool, bool]]:
    by_id = {record.id: record for record in records if record.id is not None}
    quick: list[tuple[ManagedEntityRecord, bool, bool]] = []
    seen_ids: set[int] = set()

    for entity_id in recent_ids[:1]:
        record = by_id.get(entity_id)
        if not record or record.id in seen_ids:
            continue
        seen_ids.add(record.id)
        quick.append((record, record.id in favorite_ids, True))
        if len(quick) >= limit:
            return quick

    favorite_records = sorted(
        [record for record in records if record.id in favorite_ids and record.id not in seen_ids],
        key=lambda item: (
            recent_ids.index(item.id) if item.id in recent_ids else 9999,
            (item.title or item.chat_identifier).lower(),
        ),
    )
    for record in favorite_records:
        seen_ids.add(record.id)
        quick.append((record, True, record.id in recent_ids))
        if len(quick) >= limit:
            return quick

    return quick[:limit]


class TargetPreferencesService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def get_favorite_ids(self, telegram_user_id: int) -> set[int]:
        if not self.redis_client:
            return set()
        payload = await asyncio.to_thread(self.redis_client.get, self._favorite_key(telegram_user_id))
        if not payload:
            return set()
        data = json.loads(payload)
        return {int(item) for item in data if str(item).isdigit()}

    async def get_recent_ids(self, telegram_user_id: int) -> list[int]:
        if not self.redis_client:
            return []
        payload = await asyncio.to_thread(self.redis_client.get, self._recent_key(telegram_user_id))
        if not payload:
            return []
        data = json.loads(payload)
        return [int(item) for item in data if str(item).isdigit()]

    async def toggle_favorite(self, telegram_user_id: int, entity_id: int) -> set[int]:
        favorite_ids = await self.get_favorite_ids(telegram_user_id)
        if entity_id in favorite_ids:
            favorite_ids.remove(entity_id)
        else:
            favorite_ids.add(entity_id)
        await self._set_favorites(telegram_user_id, favorite_ids)
        return favorite_ids

    async def record_recent(self, telegram_user_id: int, entity_id: int) -> list[int]:
        recent_ids = [item for item in await self.get_recent_ids(telegram_user_id) if item != entity_id]
        recent_ids.insert(0, entity_id)
        recent_ids = recent_ids[:6]
        await self._set_recents(telegram_user_id, recent_ids)
        return recent_ids

    async def rank_channels(
        self,
        telegram_user_id: int,
        records: list[ManagedEntityRecord],
    ) -> list[tuple[ManagedEntityRecord, bool, bool]]:
        favorite_ids = await self.get_favorite_ids(telegram_user_id)
        recent_ids = await self.get_recent_ids(telegram_user_id)
        return rank_channel_records(records, favorite_ids, recent_ids)

    async def quick_channels(
        self,
        telegram_user_id: int,
        records: list[ManagedEntityRecord],
        limit: int = 3,
    ) -> list[tuple[ManagedEntityRecord, bool, bool]]:
        favorite_ids = await self.get_favorite_ids(telegram_user_id)
        recent_ids = await self.get_recent_ids(telegram_user_id)
        return build_quick_pick_records(records, favorite_ids, recent_ids, limit)

    async def set_search_context(self, telegram_user_id: int, context: str) -> None:
        if not self.redis_client:
            return
        payload = json.dumps(asdict(TargetSearchContext(context=context)))
        await asyncio.to_thread(
            self.redis_client.setex,
            self._search_key(telegram_user_id),
            600,
            payload,
        )

    async def get_search_context(self, telegram_user_id: int) -> str | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._search_key(telegram_user_id))
        if not payload:
            return None
        data = json.loads(payload)
        return data.get("context")

    async def clear_search_context(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._search_key(telegram_user_id))

    async def _set_favorites(self, telegram_user_id: int, favorite_ids: set[int]) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._favorite_key(telegram_user_id),
            86400 * 30,
            json.dumps(sorted(favorite_ids)),
        )

    async def _set_recents(self, telegram_user_id: int, recent_ids: list[int]) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._recent_key(telegram_user_id),
            86400 * 30,
            json.dumps(recent_ids),
        )

    @staticmethod
    def _favorite_key(telegram_user_id: int) -> str:
        return f"em:target:favorites:{telegram_user_id}"

    @staticmethod
    def _recent_key(telegram_user_id: int) -> str:
        return f"em:target:recent:{telegram_user_id}"

    @staticmethod
    def _search_key(telegram_user_id: int) -> str:
        return f"em:target:search:{telegram_user_id}"


@dataclass(slots=True)
class TargetSearchContext:
    context: str
