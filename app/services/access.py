from __future__ import annotations

import asyncio
import logging

from aiogram.types import User

from app.core.runtime import AppContext
from app.models.access import AccessProfile, UserRecord
from app.models.audit import AuditLogRecord
from app.repositories.access import AccessRepository
from app.repositories.audit import AuditRepository

logger = logging.getLogger(__name__)


class AccessService:
    def __init__(self, app_context: AppContext) -> None:
        self.app_context = app_context

    async def build_access_profile(self, telegram_user: User) -> AccessProfile:
        if telegram_user.id in self.app_context.settings.owner_ids:
            return self._fallback_profile(telegram_user)

        if not self.app_context.oracle_client:
            return self._fallback_profile(telegram_user)

        return await asyncio.to_thread(self._build_profile_with_db, telegram_user)

    async def can_open_admin_ui(self, telegram_user: User) -> bool:
        profile = await self.build_access_profile(telegram_user)
        return profile.is_admin

    async def record_event(
        self,
        actor_user_id: int | None,
        action_key: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: str | None = None,
    ) -> None:
        if not self.app_context.oracle_client:
            return

        try:
            await asyncio.to_thread(
                AuditRepository(self.app_context.oracle_client).insert,
                AuditLogRecord(
                    actor_user_id=actor_user_id,
                    action_key=action_key,
                    target_type=target_type,
                    target_id=target_id,
                    details=details,
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for action=%s", action_key)

    def _build_profile_with_db(self, telegram_user: User) -> AccessProfile:
        repository = AccessRepository(self.app_context.oracle_client)
        if not self.app_context.core_roles_ready:
            repository.ensure_core_roles()
            self.app_context.core_roles_ready = True
        user = repository.upsert_user(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            display_name=telegram_user.full_name,
        )

        if telegram_user.id in self.app_context.settings.owner_ids:
            repository.assign_role_by_key(user.id, "OWNER")

        role_keys = repository.get_role_keys_for_user(user.id)
        return AccessProfile(user=user, role_keys=role_keys)

    def _fallback_profile(self, telegram_user: User) -> AccessProfile:
        role_keys: set[str] = set()
        if telegram_user.id in self.app_context.settings.owner_ids:
            role_keys.add("OWNER")

        return AccessProfile(
            user=UserRecord(
                id=None,
                telegram_user_id=telegram_user.id,
                username=telegram_user.username,
                display_name=telegram_user.full_name,
            ),
            role_keys=role_keys,
        )
