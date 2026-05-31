from __future__ import annotations

from typing import Any

from app.db.oracle import OracleClient
from app.models.access import RoleRecord, UserRecord, UserRoleSummary


class AccessRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def ensure_core_roles(self) -> None:
        roles = [
            {"role_key": "OWNER", "role_name": "Owner"},
            {"role_key": "SUPER_ADMIN", "role_name": "Super Admin"},
            {"role_key": "CHANNEL_MANAGER", "role_name": "Channel Manager"},
            {"role_key": "GROUP_MANAGER", "role_name": "Group Manager"},
            {"role_key": "MODERATOR", "role_name": "Moderator"},
            {"role_key": "VIEWER", "role_name": "Viewer"},
        ]
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                for role in roles:
                    cursor.execute(
                        """
                        MERGE INTO EM_ROLES target
                        USING (
                            SELECT
                                :role_key AS ROLE_KEY,
                                :role_name AS ROLE_NAME
                            FROM dual
                        ) source
                        ON (target.ROLE_KEY = source.ROLE_KEY)
                        WHEN NOT MATCHED THEN
                            INSERT (ROLE_KEY, ROLE_NAME, CREATED_AT)
                            VALUES (source.ROLE_KEY, source.ROLE_NAME, CURRENT_TIMESTAMP)
                        """,
                        role,
                    )
            connection.commit()

    def upsert_user(
        self,
        telegram_user_id: int,
        username: str | None,
        display_name: str | None,
    ) -> UserRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    MERGE INTO EM_USERS target
                    USING (
                        SELECT
                            :telegram_user_id AS TELEGRAM_USER_ID,
                            :username AS USERNAME,
                            :display_name AS DISPLAY_NAME
                        FROM dual
                    ) source
                    ON (target.TELEGRAM_USER_ID = source.TELEGRAM_USER_ID)
                    WHEN MATCHED THEN
                        UPDATE SET
                            USERNAME = source.USERNAME,
                            DISPLAY_NAME = source.DISPLAY_NAME,
                            UPDATED_AT = CURRENT_TIMESTAMP
                    WHEN NOT MATCHED THEN
                        INSERT (
                            TELEGRAM_USER_ID,
                            USERNAME,
                            DISPLAY_NAME,
                            CREATED_AT,
                            UPDATED_AT
                        )
                        VALUES (
                            source.TELEGRAM_USER_ID,
                            source.USERNAME,
                            source.DISPLAY_NAME,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                    """,
                    {
                        "telegram_user_id": telegram_user_id,
                        "username": username,
                        "display_name": display_name,
                    },
                )
                connection.commit()
                cursor.execute(
                    """
                    SELECT
                        ID,
                        TELEGRAM_USER_ID,
                        USERNAME,
                        DISPLAY_NAME,
                        CREATED_AT,
                        UPDATED_AT
                    FROM EM_USERS
                    WHERE TELEGRAM_USER_ID = :telegram_user_id
                    """,
                    {"telegram_user_id": telegram_user_id},
                )
                row = cursor.fetchone()
        return self._user_from_row(row)

    def get_user_by_telegram_id(self, telegram_user_id: int) -> UserRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        TELEGRAM_USER_ID,
                        USERNAME,
                        DISPLAY_NAME,
                        CREATED_AT,
                        UPDATED_AT
                    FROM EM_USERS
                    WHERE TELEGRAM_USER_ID = :telegram_user_id
                    """,
                    {"telegram_user_id": telegram_user_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        return self._user_from_row(row)

    def get_role_keys_for_user(self, user_id: int) -> set[str]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.ROLE_KEY
                    FROM EM_USER_ROLES ur
                    JOIN EM_ROLES r ON r.ID = ur.ROLE_ID
                    WHERE ur.USER_ID = :user_id
                    """,
                    {"user_id": user_id},
                )
                rows = cursor.fetchall()
        return {row[0] for row in rows}

    def assign_role_by_key(self, user_id: int, role_key: str) -> None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    MERGE INTO EM_USER_ROLES target
                    USING (
                        SELECT
                            :user_id AS USER_ID,
                            r.ID AS ROLE_ID
                        FROM EM_ROLES r
                        WHERE r.ROLE_KEY = :role_key
                    ) source
                    ON (
                        target.USER_ID = source.USER_ID
                        AND target.ROLE_ID = source.ROLE_ID
                    )
                    WHEN NOT MATCHED THEN
                        INSERT (USER_ID, ROLE_ID, CREATED_AT)
                        VALUES (source.USER_ID, source.ROLE_ID, CURRENT_TIMESTAMP)
                    """,
                    {"user_id": user_id, "role_key": role_key},
                )
            connection.commit()

    def remove_role_by_key(self, user_id: int, role_key: str) -> None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM EM_USER_ROLES
                    WHERE USER_ID = :user_id
                    AND ROLE_ID = (
                        SELECT ID
                        FROM EM_ROLES
                        WHERE ROLE_KEY = :role_key
                    )
                    """,
                    {"user_id": user_id, "role_key": role_key},
                )
            connection.commit()

    def list_roles(self) -> list[RoleRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ID, ROLE_KEY, ROLE_NAME
                    FROM EM_ROLES
                    ORDER BY ROLE_KEY
                    """
                )
                rows = cursor.fetchall()
        return [RoleRecord(id=row[0], role_key=row[1], role_name=row[2]) for row in rows]

    def list_users_with_roles(self) -> list[UserRoleSummary]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.TELEGRAM_USER_ID,
                        u.USERNAME,
                        u.DISPLAY_NAME,
                        LISTAGG(r.ROLE_KEY, ',') WITHIN GROUP (ORDER BY r.ROLE_KEY) AS ROLE_KEYS
                    FROM EM_USERS u
                    JOIN EM_USER_ROLES ur ON ur.USER_ID = u.ID
                    JOIN EM_ROLES r ON r.ID = ur.ROLE_ID
                    GROUP BY
                        u.TELEGRAM_USER_ID,
                        u.USERNAME,
                        u.DISPLAY_NAME
                    ORDER BY u.TELEGRAM_USER_ID
                    """
                )
                rows = cursor.fetchall()
        return [
            UserRoleSummary(
                telegram_user_id=row[0],
                username=row[1],
                display_name=row[2],
                role_keys=[item for item in (row[3] or "").split(",") if item],
            )
            for row in rows
        ]

    def get_user_role_summary(self, telegram_user_id: int) -> UserRoleSummary | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.TELEGRAM_USER_ID,
                        u.USERNAME,
                        u.DISPLAY_NAME,
                        LISTAGG(r.ROLE_KEY, ',') WITHIN GROUP (ORDER BY r.ROLE_KEY) AS ROLE_KEYS
                    FROM EM_USERS u
                    LEFT JOIN EM_USER_ROLES ur ON ur.USER_ID = u.ID
                    LEFT JOIN EM_ROLES r ON r.ID = ur.ROLE_ID
                    WHERE u.TELEGRAM_USER_ID = :telegram_user_id
                    GROUP BY
                        u.TELEGRAM_USER_ID,
                        u.USERNAME,
                        u.DISPLAY_NAME
                    """,
                    {"telegram_user_id": telegram_user_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        return UserRoleSummary(
            telegram_user_id=row[0],
            username=row[1],
            display_name=row[2],
            role_keys=[item for item in (row[3] or "").split(",") if item],
        )

    @staticmethod
    def _user_from_row(row: Any) -> UserRecord:
        return UserRecord(
            id=row[0],
            telegram_user_id=row[1],
            username=row[2],
            display_name=row[3],
            created_at=row[4],
            updated_at=row[5],
        )
