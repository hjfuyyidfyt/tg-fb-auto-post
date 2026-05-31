from app.db.oracle import OracleClient
from app.models.audit import AuditLogRecord


class AuditRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def insert(self, record: AuditLogRecord) -> None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO EM_AUDIT_LOGS (
                        ACTOR_USER_ID,
                        ACTION_KEY,
                        TARGET_TYPE,
                        TARGET_ID,
                        DETAILS,
                        CREATED_AT
                    ) VALUES (
                        :actor_user_id,
                        :action_key,
                        :target_type,
                        :target_id,
                        :details,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    {
                        "actor_user_id": record.actor_user_id,
                        "action_key": record.action_key,
                        "target_type": record.target_type,
                        "target_id": record.target_id,
                        "details": record.details,
                    },
                )
            connection.commit()

    def list_recent(self, limit: int = 10) -> list[tuple]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        ACTOR_USER_ID,
                        ACTION_KEY,
                        TARGET_TYPE,
                        TARGET_ID,
                        DETAILS,
                        CREATED_AT
                    FROM EM_AUDIT_LOGS
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST {int(limit)} ROWS ONLY
                    """
                )
                return [self._normalize_row(row) for row in cursor.fetchall()]

    def list_recent_for_target(self, target_type: str, target_id: str, limit: int = 10) -> list[tuple]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        ACTOR_USER_ID,
                        ACTION_KEY,
                        TARGET_TYPE,
                        TARGET_ID,
                        DETAILS,
                        CREATED_AT
                    FROM EM_AUDIT_LOGS
                    WHERE TARGET_TYPE = :target_type
                    AND TARGET_ID = :target_id
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST {int(limit)} ROWS ONLY
                    """,
                    {"target_type": target_type, "target_id": target_id},
                )
                return [self._normalize_row(row) for row in cursor.fetchall()]

    @staticmethod
    def _normalize_row(row: tuple) -> tuple:
        normalized: list[object] = []
        for item in row:
            if hasattr(item, "read"):
                normalized.append(item.read())
            else:
                normalized.append(item)
        return tuple(normalized)
