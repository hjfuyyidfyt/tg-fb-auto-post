from __future__ import annotations

from typing import Any

from app.db.oracle import OracleClient
from app.models.bots import ManagedBotRecord


class ManagedBotRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def add_bot(
        self,
        bot_username: str,
        display_name: str | None,
        healthcheck_url: str | None,
        action_url: str | None,
        action_method: str | None,
        action_payload_template: str | None,
        action_presets_json: str | None,
        action_auth_header: str | None,
        action_secret: str | None,
        notes: str | None,
        created_by_user_id: int | None,
    ) -> ManagedBotRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    MERGE INTO EM_MANAGED_BOTS target
                    USING (
                        SELECT
                            :bot_username AS BOT_USERNAME,
                            :display_name AS DISPLAY_NAME,
                            :healthcheck_url AS HEALTHCHECK_URL,
                            :action_url AS ACTION_URL,
                            :action_method AS ACTION_METHOD,
                            :action_payload_template AS ACTION_PAYLOAD_TEMPLATE,
                            :action_presets_json AS ACTION_PRESETS_JSON,
                            :action_auth_header AS ACTION_AUTH_HEADER,
                            :action_secret AS ACTION_SECRET,
                            :notes AS NOTES,
                            :created_by_user_id AS CREATED_BY_USER_ID
                        FROM dual
                    ) source
                    ON (target.BOT_USERNAME = source.BOT_USERNAME)
                    WHEN MATCHED THEN
                        UPDATE SET
                            DISPLAY_NAME = source.DISPLAY_NAME,
                            HEALTHCHECK_URL = source.HEALTHCHECK_URL,
                            ACTION_URL = source.ACTION_URL,
                            ACTION_METHOD = source.ACTION_METHOD,
                            ACTION_PAYLOAD_TEMPLATE = source.ACTION_PAYLOAD_TEMPLATE,
                            ACTION_PRESETS_JSON = source.ACTION_PRESETS_JSON,
                            ACTION_AUTH_HEADER = source.ACTION_AUTH_HEADER,
                            ACTION_SECRET = source.ACTION_SECRET,
                            NOTES = source.NOTES,
                            CREATED_BY_USER_ID = source.CREATED_BY_USER_ID
                    WHEN NOT MATCHED THEN
                        INSERT (
                            BOT_USERNAME,
                            DISPLAY_NAME,
                            HEALTHCHECK_URL,
                            ACTION_URL,
                            ACTION_METHOD,
                            ACTION_PAYLOAD_TEMPLATE,
                            ACTION_PRESETS_JSON,
                            ACTION_AUTH_HEADER,
                            ACTION_SECRET,
                            STATUS,
                            NOTES,
                            CREATED_BY_USER_ID,
                            CREATED_AT
                        )
                        VALUES (
                            source.BOT_USERNAME,
                            source.DISPLAY_NAME,
                            source.HEALTHCHECK_URL,
                            source.ACTION_URL,
                            source.ACTION_METHOD,
                            source.ACTION_PAYLOAD_TEMPLATE,
                            source.ACTION_PRESETS_JSON,
                            source.ACTION_AUTH_HEADER,
                            source.ACTION_SECRET,
                            'UNKNOWN',
                            source.NOTES,
                            source.CREATED_BY_USER_ID,
                            CURRENT_TIMESTAMP
                        )
                    """,
                    {
                        "bot_username": bot_username,
                        "display_name": display_name,
                        "healthcheck_url": healthcheck_url,
                        "action_url": action_url,
                        "action_method": action_method,
                        "action_payload_template": action_payload_template,
                        "action_presets_json": action_presets_json,
                        "action_auth_header": action_auth_header,
                        "action_secret": action_secret,
                        "notes": notes,
                        "created_by_user_id": created_by_user_id,
                    },
                )
                connection.commit()
                cursor.execute(
                    self._select_by_username_sql(),
                    {"bot_username": bot_username},
                )
                row = cursor.fetchone()
        return self._record_from_row(row)

    def list_bots(self) -> list[ManagedBotRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        BOT_USERNAME,
                        DISPLAY_NAME,
                        HEALTHCHECK_URL,
                        ACTION_URL,
                        ACTION_METHOD,
                        ACTION_PAYLOAD_TEMPLATE,
                        ACTION_PRESETS_JSON,
                        ACTION_AUTH_HEADER,
                        ACTION_SECRET,
                        STATUS,
                        NOTES,
                        CREATED_BY_USER_ID,
                        CREATED_AT,
                        LAST_CHECKED_AT
                    FROM EM_MANAGED_BOTS
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST 50 ROWS ONLY
                    """
                )
                rows = cursor.fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_by_id(self, bot_id: int) -> ManagedBotRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    self._select_by_id_sql(),
                    {"bot_id": bot_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def update_status(self, bot_id: int, status: str) -> ManagedBotRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_MANAGED_BOTS
                    SET STATUS = :status,
                        LAST_CHECKED_AT = CURRENT_TIMESTAMP
                    WHERE ID = :bot_id
                    """,
                    {"status": status, "bot_id": bot_id},
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"bot_id": bot_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def update_bot(
        self,
        bot_id: int,
        display_name: str | None,
        healthcheck_url: str | None,
        action_url: str | None,
        action_method: str | None,
        action_payload_template: str | None,
        action_presets_json: str | None,
        action_auth_header: str | None,
        action_secret: str | None,
        notes: str | None,
    ) -> ManagedBotRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_MANAGED_BOTS
                    SET DISPLAY_NAME = :display_name,
                        HEALTHCHECK_URL = :healthcheck_url,
                        ACTION_URL = :action_url,
                        ACTION_METHOD = :action_method,
                        ACTION_PAYLOAD_TEMPLATE = :action_payload_template,
                        ACTION_PRESETS_JSON = :action_presets_json,
                        ACTION_AUTH_HEADER = :action_auth_header,
                        ACTION_SECRET = :action_secret,
                        NOTES = :notes
                    WHERE ID = :bot_id
                    """,
                    {
                        "bot_id": bot_id,
                        "display_name": display_name,
                        "healthcheck_url": healthcheck_url,
                        "action_url": action_url,
                        "action_method": action_method,
                        "action_payload_template": action_payload_template,
                        "action_presets_json": action_presets_json,
                        "action_auth_header": action_auth_header,
                        "action_secret": action_secret,
                        "notes": notes,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"bot_id": bot_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    @staticmethod
    def _select_by_username_sql() -> str:
        return """
        SELECT
            ID,
            BOT_USERNAME,
            DISPLAY_NAME,
            HEALTHCHECK_URL,
            ACTION_URL,
            ACTION_METHOD,
            ACTION_PAYLOAD_TEMPLATE,
            ACTION_PRESETS_JSON,
            ACTION_AUTH_HEADER,
            ACTION_SECRET,
            STATUS,
            NOTES,
            CREATED_BY_USER_ID,
            CREATED_AT,
            LAST_CHECKED_AT
        FROM EM_MANAGED_BOTS
        WHERE BOT_USERNAME = :bot_username
        """

    @staticmethod
    def _select_by_id_sql() -> str:
        return """
        SELECT
            ID,
            BOT_USERNAME,
            DISPLAY_NAME,
            HEALTHCHECK_URL,
            ACTION_URL,
            ACTION_METHOD,
            ACTION_PAYLOAD_TEMPLATE,
            ACTION_PRESETS_JSON,
            ACTION_AUTH_HEADER,
            ACTION_SECRET,
            STATUS,
            NOTES,
            CREATED_BY_USER_ID,
            CREATED_AT,
            LAST_CHECKED_AT
        FROM EM_MANAGED_BOTS
        WHERE ID = :bot_id
        """

    @staticmethod
    def _record_from_row(row: Any) -> ManagedBotRecord:
        return ManagedBotRecord(
            id=row[0],
            bot_username=row[1],
            display_name=row[2],
            healthcheck_url=row[3],
            action_url=row[4],
            action_method=row[5],
            action_payload_template=row[6],
            action_presets_json=row[7],
            action_auth_header=row[8],
            action_secret=row[9],
            status=row[10],
            notes=row[11],
            created_by_user_id=row[12],
            created_at=row[13],
            last_checked_at=row[14],
        )
