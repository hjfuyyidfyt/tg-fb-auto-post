from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json

from app.core.runtime import AppContext
from app.models.entities import ManagedEntityRecord
from app.repositories.entities import ManagedEntityRepository


@dataclass(slots=True)
class PendingEntityAction:
    section: str
    action: str


class ManagedEntityService:
    def __init__(self, app_context: AppContext, redis_client: object | None = None) -> None:
        self.app_context = app_context
        self.redis_client = redis_client

    async def set_pending_action(self, telegram_user_id: int, section: str, action: str) -> None:
        if not self.redis_client:
            return

        payload = json.dumps(asdict(PendingEntityAction(section=section, action=action)))
        await asyncio.to_thread(
            self.redis_client.setex,
            self._pending_key(telegram_user_id),
            600,
            payload,
        )

    async def pop_pending_action(self, telegram_user_id: int) -> PendingEntityAction | None:
        if not self.redis_client:
            return None

        key = self._pending_key(telegram_user_id)
        payload = await asyncio.to_thread(self.redis_client.get, key)
        if not payload:
            return None

        await asyncio.to_thread(self.redis_client.delete, key)
        data = json.loads(payload)
        return PendingEntityAction(section=data["section"], action=data["action"])

    async def get_pending_action(self, telegram_user_id: int) -> PendingEntityAction | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._pending_key(telegram_user_id))
        if not payload:
            return None
        data = json.loads(payload)
        return PendingEntityAction(section=data["section"], action=data["action"])

    async def clear_pending_action(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._pending_key(telegram_user_id))

    async def add_channel(
        self,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None,
        status: str = "ACTIVE",
    ) -> ManagedEntityRecord | None:
        if not self.app_context.oracle_client:
            return None

        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.add_channel,
            chat_identifier,
            title,
            added_by_user_id,
            status,
        )

    async def add_group(
        self,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None,
        status: str = "ACTIVE",
    ) -> ManagedEntityRecord | None:
        if not self.app_context.oracle_client:
            return None

        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.add_group,
            chat_identifier,
            title,
            added_by_user_id,
            status,
        )

    async def list_channels(self) -> list[ManagedEntityRecord]:
        if not self.app_context.oracle_client:
            return []

        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_channels)

    async def list_groups(self) -> list[ManagedEntityRecord]:
        if not self.app_context.oracle_client:
            return []

        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_groups)

    async def list_channels_by_status(self, status: str) -> list[ManagedEntityRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_channels_by_status, status)

    async def list_groups_by_status(self, status: str) -> list[ManagedEntityRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ManagedEntityRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_groups_by_status, status)

    async def update_status(
        self,
        section: str,
        entity_id: int,
        status: str,
    ) -> ManagedEntityRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ManagedEntityRepository(self.app_context.oracle_client)
        if section == "Channels":
            return await asyncio.to_thread(repository.update_channel_status, entity_id, status)
        return await asyncio.to_thread(repository.update_group_status, entity_id, status)

    async def get_entity(self, section: str, entity_id: int) -> ManagedEntityRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ManagedEntityRepository(self.app_context.oracle_client)
        if section == "Channels":
            return await asyncio.to_thread(repository.get_channel_by_id, entity_id)
        return await asyncio.to_thread(repository.get_group_by_id, entity_id)

    async def detect_entity(
        self,
        section: str,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None = None,
        status: str = "PENDING",
    ) -> ManagedEntityRecord | None:
        if section == "Channels":
            return await self.add_channel(chat_identifier, title, added_by_user_id, status=status)
        return await self.add_group(chat_identifier, title, added_by_user_id, status=status)

    async def mark_removed(self, section: str, chat_identifier: str) -> ManagedEntityRecord | None:
        if not self.app_context.oracle_client:
            return None

        status_records = []
        if section == "Channels":
            status_records = await self.list_channels_by_status("ACTIVE")
            status_records += await self.list_channels_by_status("PENDING")
            status_records += await self.list_channels_by_status("IGNORED")
            status_records += await self.list_channels_by_status("BLOCKED")
        else:
            status_records = await self.list_groups_by_status("ACTIVE")
            status_records += await self.list_groups_by_status("PENDING")
            status_records += await self.list_groups_by_status("IGNORED")
            status_records += await self.list_groups_by_status("BLOCKED")

        for record in status_records:
            if record.chat_identifier == chat_identifier:
                return await self.update_status(section, record.id, "REMOVED")
        return None

    @staticmethod
    def parse_entity_input(text: str) -> tuple[str, str | None]:
        parts = [part.strip() for part in text.split("|", maxsplit=1)]
        identifier = parts[0]
        title = parts[1] if len(parts) > 1 and parts[1] else None
        return identifier, title

    @staticmethod
    def _pending_key(telegram_user_id: int) -> str:
        return f"em:pending:{telegram_user_id}"
