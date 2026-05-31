from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.oracle import OracleClient

logger = logging.getLogger(__name__)

import asyncio

class AIMemoryRepository:
    def __init__(self, oracle_client: "OracleClient | None") -> None:
        self.oracle_client = oracle_client

    async def save_preference(self, telegram_user_id: int, key: str, value: str) -> bool:
        if not self.oracle_client:
            return False
            
        sql = """
            MERGE INTO EM_AI_PREFERENCES pref
            USING (SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_user_id) usr
            ON (pref.USER_ID = usr.ID AND pref.PREFERENCE_KEY = :pref_key)
            WHEN MATCHED THEN 
                UPDATE SET pref.PREFERENCE_VALUE = :pref_value, pref.UPDATED_AT = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (USER_ID, PREFERENCE_KEY, PREFERENCE_VALUE) 
                VALUES (usr.ID, :pref_key, :pref_value)
        """
        
        def _do_save():
            with self.oracle_client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {"tg_user_id": telegram_user_id, "pref_key": key[:255], "pref_value": value})
                conn.commit()

        try:
            await asyncio.to_thread(_do_save)
            return True
        except Exception as e:
            logger.error(f"Failed to save AI preference: {e}")
            return False

    async def forget_preference(self, telegram_user_id: int, key: str) -> bool:
        if not self.oracle_client:
            return False
            
        sql = """
            DELETE FROM EM_AI_PREFERENCES 
            WHERE PREFERENCE_KEY = :pref_key 
            AND USER_ID = (SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_user_id)
        """
        
        def _do_forget():
            with self.oracle_client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {"tg_user_id": telegram_user_id, "pref_key": key[:255]})
                conn.commit()

        try:
            await asyncio.to_thread(_do_forget)
            return True
        except Exception as e:
            logger.error(f"Failed to forget AI preference: {e}")
            return False

    async def get_all_preferences(self, telegram_user_id: int) -> dict[str, str]:
        if not self.oracle_client:
            return {}
            
        sql = """
            SELECT p.PREFERENCE_KEY, p.PREFERENCE_VALUE 
            FROM EM_AI_PREFERENCES p
            JOIN EM_USERS u ON p.USER_ID = u.ID
            WHERE u.TELEGRAM_USER_ID = :tg_user_id
        """
        
        def _do_get():
            with self.oracle_client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {"tg_user_id": telegram_user_id})
                    return cur.fetchall()

        try:
            rows = await asyncio.to_thread(_do_get)
            return {str(row[0]): str(row[1]) for row in rows} if rows else {}
        except Exception as e:
            logger.error(f"Failed to get AI preferences: {e}")
            return {}

    async def log_action(self, telegram_user_id: int, action_type: str, details: str) -> None:
        if not self.oracle_client:
            return
            
        sql = """
            INSERT INTO EM_AI_LOGS (USER_ID, ACTION_TYPE, ACTION_DETAILS)
            VALUES ((SELECT ID FROM EM_USERS WHERE TELEGRAM_USER_ID = :tg_user_id), :act_type, :details)
        """
        
        def _do_log():
            with self.oracle_client.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {"tg_user_id": telegram_user_id, "act_type": action_type[:100], "details": details})
                conn.commit()

        try:
            await asyncio.to_thread(_do_log)
        except Exception as e:
            logger.error(f"Failed to log AI action: {e}")
