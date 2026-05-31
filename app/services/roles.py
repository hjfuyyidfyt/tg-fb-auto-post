from __future__ import annotations

import asyncio

from app.core.runtime import AppContext
from app.models.access import RoleRecord, UserRecord, UserRoleSummary
from app.repositories.access import AccessRepository


class RoleManagementService:
    def __init__(self, app_context: AppContext) -> None:
        self.app_context = app_context

    async def list_roles(self) -> list[RoleRecord]:
        if not self.app_context.oracle_client:
            return []

        repository = AccessRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_roles)

    async def grant_role_by_telegram_id(self, telegram_user_id: int, role_key: str) -> UserRecord | None:
        if not self.app_context.oracle_client:
            return None

        repository = AccessRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(self._grant_role_sync, repository, telegram_user_id, role_key)

    async def revoke_role_by_telegram_id(self, telegram_user_id: int, role_key: str) -> UserRecord | None:
        if not self.app_context.oracle_client:
            return None

        repository = AccessRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(self._revoke_role_sync, repository, telegram_user_id, role_key)

    async def list_users_with_roles(self) -> list[UserRoleSummary]:
        if not self.app_context.oracle_client:
            return []
        repository = AccessRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_users_with_roles)

    async def get_user_role_summary(self, telegram_user_id: int) -> UserRoleSummary | None:
        if not self.app_context.oracle_client:
            return None
        repository = AccessRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.get_user_role_summary, telegram_user_id)

    @staticmethod
    def _grant_role_sync(
        repository: AccessRepository,
        telegram_user_id: int,
        role_key: str,
    ) -> UserRecord:
        user = repository.get_user_by_telegram_id(telegram_user_id)
        if not user:
            user = repository.upsert_user(
                telegram_user_id=telegram_user_id,
                username=None,
                display_name=None,
            )
        repository.assign_role_by_key(user.id, role_key)
        return user

    @staticmethod
    def _revoke_role_sync(
        repository: AccessRepository,
        telegram_user_id: int,
        role_key: str,
    ) -> UserRecord | None:
        user = repository.get_user_by_telegram_id(telegram_user_id)
        if not user:
            return None
        repository.remove_role_by_key(user.id, role_key)
        return user
