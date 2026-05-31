from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
import calendar
from zoneinfo import ZoneInfo

from app.core.runtime import AppContext
from app.models.schedule import ScheduledPostRecord
from app.repositories.schedule import ScheduledPostRepository
from app.services.schedule_utils import ParsedScheduleSpec, next_occurrence, parse_schedule_time


@dataclass(slots=True)
class PendingScheduleAction:
    stage: str
    channel_identifier: str
    channel_title: str | None
    scheduled_for: str | None = None
    recurrence_key: str | None = None
    schedule_mode: str | None = None
    draft_message_text: str | None = None
    draft_media_path: str | None = None
    draft_media_name: str | None = None
    draft_media_type: str | None = None
    selected_weekday: int | None = None
    selected_monthday: int | None = None


class ScheduleService:
    DASHBOARD_TIMEZONE = ZoneInfo("Asia/Dhaka")

    def __init__(self, app_context: AppContext, redis_client: object | None = None) -> None:
        self.app_context = app_context
        self.redis_client = redis_client

    async def start_schedule(
        self,
        telegram_user_id: int,
        channel_identifier: str,
        channel_title: str | None,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_time",
                channel_identifier=channel_identifier,
                channel_title=channel_title,
            ),
        )

    async def get_pending(self, telegram_user_id: int) -> PendingScheduleAction | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._schedule_key(telegram_user_id))
        if not payload:
            return None
        data = json.loads(payload)
        return PendingScheduleAction(**data)

    async def advance_to_message(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
        scheduled_for: str,
        recurrence_key: str | None,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_message",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=scheduled_for,
                recurrence_key=recurrence_key,
                schedule_mode=pending.schedule_mode,
                draft_message_text=None,
                draft_media_path=None,
                draft_media_name=None,
                draft_media_type=None,
                selected_weekday=pending.selected_weekday,
                selected_monthday=pending.selected_monthday,
            ),
        )

    async def set_schedule_mode(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
        schedule_mode: str,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_time",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=None,
                recurrence_key=None,
                schedule_mode=schedule_mode,
                draft_message_text=None,
                draft_media_path=None,
                draft_media_name=None,
                draft_media_type=None,
                selected_weekday=None,
                selected_monthday=None,
            ),
        )

    async def set_weekday(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
        weekday: int,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_time",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=None,
                recurrence_key=None,
                schedule_mode=pending.schedule_mode,
                draft_message_text=None,
                draft_media_path=None,
                draft_media_name=None,
                draft_media_type=None,
                selected_weekday=weekday,
                selected_monthday=None,
            ),
        )

    async def set_monthday(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
        monthday: int,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_time",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=None,
                recurrence_key=None,
                schedule_mode=pending.schedule_mode,
                draft_message_text=None,
                draft_media_path=None,
                draft_media_name=None,
                draft_media_type=None,
                selected_weekday=None,
                selected_monthday=monthday,
            ),
        )

    async def set_draft_content(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
        message_text: str,
        media_path: str | None = None,
        media_name: str | None = None,
        media_type: str | None = None,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_confirm",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=pending.scheduled_for,
                recurrence_key=pending.recurrence_key,
                schedule_mode=pending.schedule_mode,
                draft_message_text=message_text,
                draft_media_path=media_path,
                draft_media_name=media_name,
                draft_media_type=media_type,
                selected_weekday=pending.selected_weekday,
                selected_monthday=pending.selected_monthday,
            ),
        )

    async def return_to_time_step(
        self,
        telegram_user_id: int,
        pending: PendingScheduleAction,
    ) -> None:
        await self._set_pending(
            telegram_user_id,
            PendingScheduleAction(
                stage="await_time",
                channel_identifier=pending.channel_identifier,
                channel_title=pending.channel_title,
                scheduled_for=None,
                recurrence_key=None,
                schedule_mode=pending.schedule_mode,
                draft_message_text=None,
                draft_media_path=None,
                draft_media_name=None,
                draft_media_type=None,
                selected_weekday=pending.selected_weekday,
                selected_monthday=pending.selected_monthday,
            ),
        )

    async def clear_pending(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._schedule_key(telegram_user_id))

    async def create_scheduled_post(
        self,
        pending: PendingScheduleAction,
        message_text: str,
        created_by_user_id: int | None,
        media_path: str | None = None,
        media_name: str | None = None,
        media_type: str | None = None,
    ) -> ScheduledPostRecord | None:
        if not self.app_context.oracle_client:
            return None

        scheduled_for = datetime.strptime(pending.scheduled_for, "%Y-%m-%d %H:%M")
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.create,
            pending.channel_identifier,
            pending.channel_title,
            message_text,
            scheduled_for,
            pending.recurrence_key,
            media_path,
            media_name,
            media_type,
            created_by_user_id,
        )

    async def create_direct(
        self,
        channel_identifier: str,
        channel_title: str | None,
        scheduled_for_raw: str,
        message_text: str,
        created_by_user_id: int | None,
        media_path: str | None = None,
        media_name: str | None = None,
        media_type: str | None = None,
    ) -> ScheduledPostRecord | None:
        if not self.app_context.oracle_client:
            return None

        parsed = self.parse_schedule_time(scheduled_for_raw)
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.create,
            channel_identifier,
            channel_title,
            message_text,
            parsed.scheduled_for,
            parsed.recurrence_key,
            media_path,
            media_name,
            media_type,
            created_by_user_id,
        )

    async def list_pending(self) -> list[ScheduledPostRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_pending)

    async def list_paused(self) -> list[ScheduledPostRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_paused)

    async def list_manageable(self) -> list[ScheduledPostRecord]:
        pending = await self.list_pending()
        paused = await self.list_paused()
        return sorted(pending + paused, key=lambda item: (item.scheduled_for, item.id or 0))

    async def list_failed(self) -> list[ScheduledPostRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_failed)

    async def list_recent_history(self, limit: int = 30) -> list[ScheduledPostRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_recent_history, limit)

    async def get_by_id(self, schedule_id: int) -> ScheduledPostRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.get_by_id, schedule_id)

    async def list_due_pending(self) -> list[ScheduledPostRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        records = await asyncio.to_thread(repository.list_due_pending)
        now_local = datetime.now(self.DASHBOARD_TIMEZONE).replace(tzinfo=None)
        return [item for item in records if item.scheduled_for and item.scheduled_for <= now_local]

    async def update_status(self, schedule_id: int, status: str) -> None:
        if not self.app_context.oracle_client:
            return
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        await asyncio.to_thread(repository.update_status, schedule_id, status)

    async def reschedule_post(self, schedule_id: int, scheduled_for: datetime) -> None:
        if not self.app_context.oracle_client:
            return
        repository = ScheduledPostRepository(self.app_context.oracle_client)
        await asyncio.to_thread(repository.reschedule, schedule_id, scheduled_for)

    async def skip_next(self, schedule_id: int) -> ScheduledPostRecord | None:
        record = await self.get_by_id(schedule_id)
        if not record:
            return None
        next_run = self.next_occurrence(record)
        if not next_run:
            return None
        await self.reschedule_post(schedule_id, next_run)
        return await self.get_by_id(schedule_id)

    async def _set_pending(self, telegram_user_id: int, action: PendingScheduleAction) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(
            self.redis_client.setex,
            self._schedule_key(telegram_user_id),
            1800,
            json.dumps(asdict(action)),
        )

    @staticmethod
    def _schedule_key(telegram_user_id: int) -> str:
        return f"em:schedule:{telegram_user_id}"

    @staticmethod
    def parse_schedule_time(value: str) -> ParsedScheduleSpec:
        return parse_schedule_time(value, ScheduleService.DASHBOARD_TIMEZONE)

    @staticmethod
    def next_occurrence(record: ScheduledPostRecord) -> datetime | None:
        return next_occurrence(record)
