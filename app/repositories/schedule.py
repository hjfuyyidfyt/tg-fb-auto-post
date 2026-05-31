from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db.oracle import OracleClient
from app.models.schedule import ScheduledPostRecord


class ScheduledPostRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def create(
        self,
        channel_identifier: str,
        channel_title: str | None,
        message_text: str,
        scheduled_for: datetime,
        recurrence_key: str | None,
        media_path: str | None,
        media_name: str | None,
        media_type: str | None,
        created_by_user_id: int | None,
    ) -> ScheduledPostRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                out_id = cursor.var(int)
                out_channel_identifier = cursor.var(str)
                out_channel_title = cursor.var(str)
                out_message_text = cursor.var(str)
                out_scheduled_for = cursor.var(datetime)
                out_recurrence_key = cursor.var(str)
                out_media_path = cursor.var(str)
                out_media_name = cursor.var(str)
                out_media_type = cursor.var(str)
                out_status = cursor.var(str)
                out_created_by_user_id = cursor.var(int)
                cursor.execute(
                    """
                    INSERT INTO EM_SCHEDULED_POSTS (
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID,
                        CREATED_AT
                    ) VALUES (
                        :channel_identifier,
                        :channel_title,
                        :message_text,
                        :scheduled_for,
                        :recurrence_key,
                        :media_path,
                        :media_name,
                        :media_type,
                        'PENDING',
                        :created_by_user_id,
                        CURRENT_TIMESTAMP
                    )
                    RETURNING
                        ID,
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID
                    INTO
                        :id,
                        :out_channel_identifier,
                        :out_channel_title,
                        :out_message_text,
                        :out_scheduled_for,
                        :out_recurrence_key,
                        :out_media_path,
                        :out_media_name,
                        :out_media_type,
                        :out_status,
                        :out_created_by_user_id
                    """,
                    {
                        "channel_identifier": channel_identifier,
                        "channel_title": channel_title,
                        "message_text": message_text,
                        "scheduled_for": scheduled_for,
                        "recurrence_key": recurrence_key,
                        "media_path": media_path,
                        "media_name": media_name,
                        "media_type": media_type,
                        "created_by_user_id": created_by_user_id,
                        "id": out_id,
                        "out_channel_identifier": out_channel_identifier,
                        "out_channel_title": out_channel_title,
                        "out_message_text": out_message_text,
                        "out_scheduled_for": out_scheduled_for,
                        "out_recurrence_key": out_recurrence_key,
                        "out_media_path": out_media_path,
                        "out_media_name": out_media_name,
                        "out_media_type": out_media_type,
                        "out_status": out_status,
                        "out_created_by_user_id": out_created_by_user_id,
                    },
                )
                row = (
                    out_id.getvalue()[0],
                    out_channel_identifier.getvalue()[0],
                    out_channel_title.getvalue()[0],
                    out_message_text.getvalue()[0],
                    out_scheduled_for.getvalue()[0],
                    out_recurrence_key.getvalue()[0],
                    out_media_path.getvalue()[0],
                    out_media_name.getvalue()[0],
                    out_media_type.getvalue()[0],
                    out_status.getvalue()[0],
                    out_created_by_user_id.getvalue()[0],
                )
            connection.commit()
        return self._record_from_row(row)

    def list_pending(self) -> list[ScheduledPostRecord]:
        return self.list_by_status("PENDING", 20)

    def list_paused(self) -> list[ScheduledPostRecord]:
        return self.list_by_status("PAUSED", 20)

    def list_failed(self) -> list[ScheduledPostRecord]:
        return self.list_by_status("FAILED", 20)

    def list_recent_history(self, limit: int = 30) -> list[ScheduledPostRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        ID,
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID
                    FROM EM_SCHEDULED_POSTS
                    WHERE STATUS IN ('SENT', 'FAILED', 'CANCELED')
                    ORDER BY SCHEDULED_FOR DESC, ID DESC
                    FETCH FIRST {int(limit)} ROWS ONLY
                    """
                )
                rows = [self._normalize_row_data(row) for row in cursor.fetchall()]
        return [self._record_from_row(row) for row in rows]

    def list_by_status(self, status: str, limit: int = 20) -> list[ScheduledPostRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        ID,
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID
                    FROM EM_SCHEDULED_POSTS
                    WHERE STATUS = :status
                    ORDER BY SCHEDULED_FOR ASC
                    FETCH FIRST {int(limit)} ROWS ONLY
                    """,
                    {"status": status},
                )
                rows = [self._normalize_row_data(row) for row in cursor.fetchall()]
        return [self._record_from_row(row) for row in rows]

    def get_by_id(self, schedule_id: int) -> ScheduledPostRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID
                    FROM EM_SCHEDULED_POSTS
                    WHERE ID = :schedule_id
                    """,
                    {"schedule_id": schedule_id},
                )
                row = cursor.fetchone()
                if row:
                    row = self._normalize_row_data(row)
        if not row:
            return None
        return self._record_from_row(row)

    def list_due_pending(self) -> list[ScheduledPostRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        CHANNEL_IDENTIFIER,
                        CHANNEL_TITLE,
                        MESSAGE_TEXT,
                        SCHEDULED_FOR,
                        RECURRENCE_KEY,
                        MEDIA_PATH,
                        MEDIA_NAME,
                        MEDIA_TYPE,
                        STATUS,
                        CREATED_BY_USER_ID
                    FROM EM_SCHEDULED_POSTS
                    WHERE STATUS = 'PENDING'
                    ORDER BY SCHEDULED_FOR ASC
                    FETCH FIRST 50 ROWS ONLY
                    """
                )
                rows = [self._normalize_row_data(row) for row in cursor.fetchall()]
        return [self._record_from_row(row) for row in rows]

    def update_status(self, schedule_id: int, status: str) -> None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_SCHEDULED_POSTS
                    SET STATUS = :status
                    WHERE ID = :schedule_id
                    """,
                    {"status": status, "schedule_id": schedule_id},
                )
            connection.commit()

    def reschedule(self, schedule_id: int, scheduled_for: datetime) -> None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_SCHEDULED_POSTS
                    SET SCHEDULED_FOR = :scheduled_for,
                        STATUS = 'PENDING'
                    WHERE ID = :schedule_id
                    """,
                    {"scheduled_for": scheduled_for, "schedule_id": schedule_id},
                )
            connection.commit()

    @staticmethod
    def _record_from_row(row: Any) -> ScheduledPostRecord:
        return ScheduledPostRecord(
            id=row[0],
            channel_identifier=row[1],
            channel_title=row[2],
            message_text=row[3],
            scheduled_for=row[4],
            recurrence_key=row[5],
            media_path=row[6],
            media_name=row[7],
            media_type=row[8],
            status=row[9],
            created_by_user_id=row[10],
        )

    @staticmethod
    def _normalize_row_data(row: Any) -> tuple:
        values = list(row)
        for index in (2, 3):
            item = values[index]
            if hasattr(item, "read"):
                values[index] = item.read()
        return tuple(values)
