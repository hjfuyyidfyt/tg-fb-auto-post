from __future__ import annotations

from typing import Any

from app.db.oracle import OracleClient
from app.models.entities import ManagedEntityRecord


class ManagedEntityRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def add_channel(
        self,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None,
        status: str = "ACTIVE",
    ) -> ManagedEntityRecord:
        return self._upsert_entity("EM_CHANNELS", chat_identifier, title, added_by_user_id, status)

    def add_group(
        self,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None,
        status: str = "ACTIVE",
    ) -> ManagedEntityRecord:
        return self._upsert_entity("EM_GROUPS", chat_identifier, title, added_by_user_id, status)

    def list_channels(self) -> list[ManagedEntityRecord]:
        return self._list_entities("EM_CHANNELS", "ACTIVE")

    def list_groups(self) -> list[ManagedEntityRecord]:
        return self._list_entities("EM_GROUPS", "ACTIVE")

    def list_channels_by_status(self, status: str) -> list[ManagedEntityRecord]:
        return self._list_entities("EM_CHANNELS", status)

    def list_groups_by_status(self, status: str) -> list[ManagedEntityRecord]:
        return self._list_entities("EM_GROUPS", status)

    def update_channel_status(self, entity_id: int, status: str) -> ManagedEntityRecord | None:
        return self._update_status("EM_CHANNELS", entity_id, status)

    def update_group_status(self, entity_id: int, status: str) -> ManagedEntityRecord | None:
        return self._update_status("EM_GROUPS", entity_id, status)

    def get_channel_by_id(self, entity_id: int) -> ManagedEntityRecord | None:
        return self._get_by_id("EM_CHANNELS", entity_id)

    def get_group_by_id(self, entity_id: int) -> ManagedEntityRecord | None:
        return self._get_by_id("EM_GROUPS", entity_id)

    def _upsert_entity(
        self,
        table_name: str,
        chat_identifier: str,
        title: str | None,
        added_by_user_id: int | None,
        status: str,
    ) -> ManagedEntityRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    MERGE INTO {table_name} target
                    USING (
                        SELECT
                            :chat_identifier AS CHAT_IDENTIFIER,
                            :title AS TITLE,
                            :added_by_user_id AS ADDED_BY_USER_ID,
                            :status AS STATUS
                        FROM dual
                    ) source
                    ON (target.CHAT_IDENTIFIER = source.CHAT_IDENTIFIER)
                    WHEN MATCHED THEN
                        UPDATE SET
                            TITLE = source.TITLE,
                            ADDED_BY_USER_ID = source.ADDED_BY_USER_ID,
                            STATUS = source.STATUS
                    WHEN NOT MATCHED THEN
                        INSERT (
                            CHAT_IDENTIFIER,
                            TITLE,
                            ADDED_BY_USER_ID,
                            STATUS,
                            CREATED_AT
                        )
                        VALUES (
                            source.CHAT_IDENTIFIER,
                            source.TITLE,
                            source.ADDED_BY_USER_ID,
                            source.STATUS,
                            CURRENT_TIMESTAMP
                        )
                    """,
                    {
                        "chat_identifier": chat_identifier,
                        "title": title,
                        "added_by_user_id": added_by_user_id,
                        "status": status,
                    },
                )
                connection.commit()
                cursor.execute(
                    self._select_by_identifier_sql(table_name),
                    {"chat_identifier": chat_identifier},
                )
                row = cursor.fetchone()
        return self._record_from_row(row)

    def _list_entities(self, table_name: str, status: str | None = None) -> list[ManagedEntityRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                if status:
                    cursor.execute(
                        f"""
                        SELECT
                            ID,
                            CHAT_IDENTIFIER,
                            TITLE,
                            ADDED_BY_USER_ID,
                            STATUS,
                            CREATED_AT
                        FROM {table_name}
                        WHERE STATUS = :status
                        ORDER BY CREATED_AT DESC
                        FETCH FIRST 20 ROWS ONLY
                        """,
                        {"status": status},
                    )
                else:
                    cursor.execute(
                        f"""
                        SELECT
                            ID,
                            CHAT_IDENTIFIER,
                            TITLE,
                            ADDED_BY_USER_ID,
                            STATUS,
                            CREATED_AT
                        FROM {table_name}
                        ORDER BY CREATED_AT DESC
                        FETCH FIRST 20 ROWS ONLY
                        """
                    )
                rows = cursor.fetchall()
        return [self._record_from_row(row) for row in rows]

    def _update_status(self, table_name: str, entity_id: int, status: str) -> ManagedEntityRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {table_name}
                    SET STATUS = :status
                    WHERE ID = :entity_id
                    """,
                    {"status": status, "entity_id": entity_id},
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(table_name), {"entity_id": entity_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def _get_by_id(self, table_name: str, entity_id: int) -> ManagedEntityRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(self._select_by_id_sql(table_name), {"entity_id": entity_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    @staticmethod
    def _select_by_identifier_sql(table_name: str) -> str:
        return f"""
        SELECT
            ID,
            CHAT_IDENTIFIER,
            TITLE,
            ADDED_BY_USER_ID,
            STATUS,
            CREATED_AT
        FROM {table_name}
        WHERE CHAT_IDENTIFIER = :chat_identifier
        """

    @staticmethod
    def _select_by_id_sql(table_name: str) -> str:
        return f"""
        SELECT
            ID,
            CHAT_IDENTIFIER,
            TITLE,
            ADDED_BY_USER_ID,
            STATUS,
            CREATED_AT
        FROM {table_name}
        WHERE ID = :entity_id
        """

    @staticmethod
    def _record_from_row(row: Any) -> ManagedEntityRecord:
        return ManagedEntityRecord(
            id=row[0],
            chat_identifier=row[1],
            title=row[2],
            added_by_user_id=row[3],
            status=row[4],
            created_at=row[5],
        )
