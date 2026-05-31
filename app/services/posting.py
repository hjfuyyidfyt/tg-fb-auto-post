from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json


@dataclass(slots=True)
class PendingPostAction:
    channel_identifier: str
    channel_title: str | None
    stage: str = "await_content"
    draft_message_text: str | None = None
    draft_media_path: str | None = None
    draft_media_name: str | None = None
    draft_media_type: str | None = None


@dataclass(slots=True)
class PendingBroadcastAction:
    targets: list[dict[str, str | None]]
    stage: str = "await_content"
    draft_message_text: str | None = None
    draft_media_path: str | None = None
    draft_media_name: str | None = None
    draft_media_type: str | None = None


@dataclass(slots=True)
class BroadcastSelectionState:
    selected_ids: list[int]


class PostingService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    async def set_pending_post(
        self,
        telegram_user_id: int,
        channel_identifier: str,
        channel_title: str | None,
    ) -> None:
        if not self.redis_client:
            return

        payload = json.dumps(
            asdict(
                PendingPostAction(
                    channel_identifier=channel_identifier,
                    channel_title=channel_title,
                )
            )
        )
        await asyncio.to_thread(
            self.redis_client.setex,
            self._post_key(telegram_user_id),
            900,
            payload,
        )

    async def pop_pending_post(self, telegram_user_id: int) -> PendingPostAction | None:
        if not self.redis_client:
            return None

        key = self._post_key(telegram_user_id)
        payload = await asyncio.to_thread(self.redis_client.get, key)
        if not payload:
            return None

        await asyncio.to_thread(self.redis_client.delete, key)
        data = json.loads(payload)
        return PendingPostAction(**data)

    async def get_pending_post(self, telegram_user_id: int) -> PendingPostAction | None:
        if not self.redis_client:
            return None

        payload = await asyncio.to_thread(self.redis_client.get, self._post_key(telegram_user_id))
        if not payload:
            return None

        data = json.loads(payload)
        return PendingPostAction(**data)

    async def set_post_draft(
        self,
        telegram_user_id: int,
        pending: PendingPostAction,
        message_text: str,
        media_path: str | None = None,
        media_name: str | None = None,
        media_type: str | None = None,
    ) -> None:
        if not self.redis_client:
            return
        payload = json.dumps(
            asdict(
                PendingPostAction(
                    channel_identifier=pending.channel_identifier,
                    channel_title=pending.channel_title,
                    stage="await_confirm",
                    draft_message_text=message_text,
                    draft_media_path=media_path,
                    draft_media_name=media_name,
                    draft_media_type=media_type,
                )
            )
        )
        await asyncio.to_thread(self.redis_client.setex, self._post_key(telegram_user_id), 900, payload)

    async def clear_pending_post(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._post_key(telegram_user_id))

    async def set_pending_broadcast(
        self,
        telegram_user_id: int,
        targets: list[dict[str, str | None]],
    ) -> None:
        if not self.redis_client:
            return

        payload = json.dumps(asdict(PendingBroadcastAction(targets=targets)))
        await asyncio.to_thread(
            self.redis_client.setex,
            self._broadcast_key(telegram_user_id),
            900,
            payload,
        )

    async def pop_pending_broadcast(self, telegram_user_id: int) -> PendingBroadcastAction | None:
        if not self.redis_client:
            return None

        key = self._broadcast_key(telegram_user_id)
        payload = await asyncio.to_thread(self.redis_client.get, key)
        if not payload:
            return None

        await asyncio.to_thread(self.redis_client.delete, key)
        data = json.loads(payload)
        return PendingBroadcastAction(**data)

    async def get_pending_broadcast(self, telegram_user_id: int) -> PendingBroadcastAction | None:
        if not self.redis_client:
            return None

        payload = await asyncio.to_thread(self.redis_client.get, self._broadcast_key(telegram_user_id))
        if not payload:
            return None

        data = json.loads(payload)
        return PendingBroadcastAction(**data)

    async def set_broadcast_draft(
        self,
        telegram_user_id: int,
        pending: PendingBroadcastAction,
        message_text: str,
        media_path: str | None = None,
        media_name: str | None = None,
        media_type: str | None = None,
    ) -> None:
        if not self.redis_client:
            return
        payload = json.dumps(
            asdict(
                PendingBroadcastAction(
                    targets=pending.targets,
                    stage="await_confirm",
                    draft_message_text=message_text,
                    draft_media_path=media_path,
                    draft_media_name=media_name,
                    draft_media_type=media_type,
                )
            )
        )
        await asyncio.to_thread(self.redis_client.setex, self._broadcast_key(telegram_user_id), 900, payload)

    async def clear_pending_broadcast(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._broadcast_key(telegram_user_id))

    async def get_broadcast_selection(self, telegram_user_id: int) -> BroadcastSelectionState:
        if not self.redis_client:
            return BroadcastSelectionState(selected_ids=[])

        payload = await asyncio.to_thread(self.redis_client.get, self._broadcast_select_key(telegram_user_id))
        if not payload:
            return BroadcastSelectionState(selected_ids=[])
        data = json.loads(payload)
        return BroadcastSelectionState(selected_ids=data.get("selected_ids", []))

    async def toggle_broadcast_target(self, telegram_user_id: int, entity_id: int) -> BroadcastSelectionState:
        state = await self.get_broadcast_selection(telegram_user_id)
        selected = set(state.selected_ids)
        if entity_id in selected:
            selected.remove(entity_id)
        else:
            selected.add(entity_id)
        new_state = BroadcastSelectionState(selected_ids=sorted(selected))
        await self._set_broadcast_selection(telegram_user_id, new_state)
        return new_state

    async def clear_broadcast_selection(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._broadcast_select_key(telegram_user_id))

    async def _set_broadcast_selection(
        self,
        telegram_user_id: int,
        state: BroadcastSelectionState,
    ) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._broadcast_select_key(telegram_user_id),
            1800,
            json.dumps(asdict(state)),
        )

    @staticmethod
    def _post_key(telegram_user_id: int) -> str:
        return f"em:post:{telegram_user_id}"

    @staticmethod
    def _broadcast_key(telegram_user_id: int) -> str:
        return f"em:broadcast:{telegram_user_id}"

    @staticmethod
    def _broadcast_select_key(telegram_user_id: int) -> str:
        return f"em:broadcast:select:{telegram_user_id}"
