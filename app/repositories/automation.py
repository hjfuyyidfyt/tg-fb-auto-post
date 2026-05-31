from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db.oracle import OracleClient
from app.models.automation import AutomationRuleRecord


class AutomationRepository:
    def __init__(self, oracle_client: OracleClient) -> None:
        self.oracle_client = oracle_client

    def upsert_rule(
        self,
        template_key: str,
        template_name: str,
        schedule_key: str,
        config_json: str | None,
        status: str,
        created_by_user_id: int | None,
        next_run_at: datetime,
    ) -> AutomationRuleRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    MERGE INTO EM_AUTOMATIONS target
                    USING (
                        SELECT
                            :template_key AS TEMPLATE_KEY,
                            :template_name AS TEMPLATE_NAME,
                            :schedule_key AS SCHEDULE_KEY,
                            :config_json AS CONFIG_JSON,
                            :status AS STATUS,
                            :created_by_user_id AS CREATED_BY_USER_ID,
                            :next_run_at AS NEXT_RUN_AT
                        FROM dual
                    ) source
                    ON (target.TEMPLATE_KEY = source.TEMPLATE_KEY)
                    WHEN MATCHED THEN
                        UPDATE SET
                            TEMPLATE_NAME = source.TEMPLATE_NAME,
                            SCHEDULE_KEY = source.SCHEDULE_KEY,
                            CONFIG_JSON = source.CONFIG_JSON,
                            STATUS = source.STATUS,
                            CREATED_BY_USER_ID = source.CREATED_BY_USER_ID,
                            NEXT_RUN_AT = source.NEXT_RUN_AT
                    WHEN NOT MATCHED THEN
                        INSERT (
                            TEMPLATE_KEY,
                            TEMPLATE_NAME,
                            SCHEDULE_KEY,
                            CONFIG_JSON,
                            STATUS,
                            CREATED_BY_USER_ID,
                            CREATED_AT,
                            NEXT_RUN_AT
                        )
                        VALUES (
                            source.TEMPLATE_KEY,
                            source.TEMPLATE_NAME,
                            source.SCHEDULE_KEY,
                            source.CONFIG_JSON,
                            source.STATUS,
                            source.CREATED_BY_USER_ID,
                            CURRENT_TIMESTAMP,
                            source.NEXT_RUN_AT
                        )
                    """,
                    {
                        "template_key": template_key,
                        "template_name": template_name,
                        "schedule_key": schedule_key,
                        "config_json": config_json,
                        "status": status,
                        "created_by_user_id": created_by_user_id,
                        "next_run_at": next_run_at,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_template_sql(), {"template_key": template_key})
                row = cursor.fetchone()
        return self._record_from_row(row)

    def create_rule(
        self,
        template_key: str,
        template_name: str,
        schedule_key: str,
        config_json: str | None,
        status: str,
        created_by_user_id: int | None,
        next_run_at: datetime,
    ) -> AutomationRuleRecord:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO EM_AUTOMATIONS (
                        TEMPLATE_KEY,
                        TEMPLATE_NAME,
                        SCHEDULE_KEY,
                        CONFIG_JSON,
                        STATUS,
                        CREATED_BY_USER_ID,
                        CREATED_AT,
                        NEXT_RUN_AT
                    )
                    VALUES (
                        :template_key,
                        :template_name,
                        :schedule_key,
                        :config_json,
                        :status,
                        :created_by_user_id,
                        CURRENT_TIMESTAMP,
                        :next_run_at
                    )
                    """,
                    {
                        "template_key": template_key,
                        "template_name": template_name,
                        "schedule_key": schedule_key,
                        "config_json": config_json,
                        "status": status,
                        "created_by_user_id": created_by_user_id,
                        "next_run_at": next_run_at,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_template_sql(), {"template_key": template_key})
                row = cursor.fetchone()
        return self._record_from_row(row)

    def list_rules(self) -> list[AutomationRuleRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        TEMPLATE_KEY,
                        TEMPLATE_NAME,
                        SCHEDULE_KEY,
                        CONFIG_JSON,
                        STATUS,
                        CREATED_BY_USER_ID,
                        CREATED_AT,
                        LAST_RUN_AT,
                        NEXT_RUN_AT
                    FROM EM_AUTOMATIONS
                    ORDER BY CREATED_AT DESC, ID DESC
                    FETCH FIRST 50 ROWS ONLY
                    """
                )
                rows = cursor.fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_rule(self, rule_id: int) -> AutomationRuleRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(self._select_by_id_sql(), {"rule_id": rule_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def update_status(self, rule_id: int, status: str) -> AutomationRuleRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_AUTOMATIONS
                    SET STATUS = :status
                    WHERE ID = :rule_id
                    """,
                    {"status": status, "rule_id": rule_id},
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"rule_id": rule_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def delete_rule(self, rule_id: int) -> bool:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM EM_AUTOMATIONS WHERE ID = :rule_id", {"rule_id": rule_id})
                deleted = cursor.rowcount > 0
                connection.commit()
        return deleted

    def list_due_rules(self, now: datetime) -> list[AutomationRuleRecord]:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ID,
                        TEMPLATE_KEY,
                        TEMPLATE_NAME,
                        SCHEDULE_KEY,
                        CONFIG_JSON,
                        STATUS,
                        CREATED_BY_USER_ID,
                        CREATED_AT,
                        LAST_RUN_AT,
                        NEXT_RUN_AT
                    FROM EM_AUTOMATIONS
                    WHERE STATUS = 'ACTIVE'
                      AND NEXT_RUN_AT IS NOT NULL
                      AND NEXT_RUN_AT <= :now_ts
                    ORDER BY NEXT_RUN_AT ASC, ID ASC
                    """,
                    {"now_ts": now},
                )
                rows = cursor.fetchall()
        return [self._record_from_row(row) for row in rows]

    def mark_run(self, rule_id: int, last_run_at: datetime, next_run_at: datetime) -> AutomationRuleRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_AUTOMATIONS
                    SET LAST_RUN_AT = :last_run_at,
                        NEXT_RUN_AT = :next_run_at
                    WHERE ID = :rule_id
                    """,
                    {
                        "last_run_at": last_run_at,
                        "next_run_at": next_run_at,
                        "rule_id": rule_id,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"rule_id": rule_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def update_next_run(self, rule_id: int, next_run_at: datetime) -> AutomationRuleRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_AUTOMATIONS
                    SET NEXT_RUN_AT = :next_run_at
                    WHERE ID = :rule_id
                    """,
                    {
                        "next_run_at": next_run_at,
                        "rule_id": rule_id,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"rule_id": rule_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    def update_rule_definition(
        self,
        rule_id: int,
        template_name: str,
        schedule_key: str,
        config_json: str | None,
        next_run_at: datetime | None,
    ) -> AutomationRuleRecord | None:
        with self.oracle_client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE EM_AUTOMATIONS
                    SET TEMPLATE_NAME = :template_name,
                        SCHEDULE_KEY = :schedule_key,
                        CONFIG_JSON = :config_json,
                        NEXT_RUN_AT = :next_run_at
                    WHERE ID = :rule_id
                    """,
                    {
                        "template_name": template_name,
                        "schedule_key": schedule_key,
                        "config_json": config_json,
                        "next_run_at": next_run_at,
                        "rule_id": rule_id,
                    },
                )
                connection.commit()
                cursor.execute(self._select_by_id_sql(), {"rule_id": rule_id})
                row = cursor.fetchone()
        if not row:
            return None
        return self._record_from_row(row)

    @staticmethod
    def _select_by_template_sql() -> str:
        return """
        SELECT
            ID,
            TEMPLATE_KEY,
            TEMPLATE_NAME,
            SCHEDULE_KEY,
            CONFIG_JSON,
            STATUS,
            CREATED_BY_USER_ID,
            CREATED_AT,
            LAST_RUN_AT,
            NEXT_RUN_AT
        FROM EM_AUTOMATIONS
        WHERE TEMPLATE_KEY = :template_key
        """

    @staticmethod
    def _select_by_id_sql() -> str:
        return """
        SELECT
            ID,
            TEMPLATE_KEY,
            TEMPLATE_NAME,
            SCHEDULE_KEY,
            CONFIG_JSON,
            STATUS,
            CREATED_BY_USER_ID,
            CREATED_AT,
            LAST_RUN_AT,
            NEXT_RUN_AT
        FROM EM_AUTOMATIONS
        WHERE ID = :rule_id
        """

    @staticmethod
    def _record_from_row(row: Any) -> AutomationRuleRecord:
        return AutomationRuleRecord(
            id=row[0],
            template_key=row[1],
            template_name=row[2],
            schedule_key=row[3],
            config_json=row[4],
            status=row[5],
            created_by_user_id=row[6],
            created_at=row[7],
            last_run_at=row[8],
            next_run_at=row[9],
        )
