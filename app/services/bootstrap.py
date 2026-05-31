from __future__ import annotations

from app.core.config import Settings
from app.core.runtime import AppContext
from app.db.oracle import OracleClient
from app.db.redis_client import build_redis_client


def bootstrap_dependencies(settings: Settings) -> dict[str, object]:
    oracle_client = None
    if settings.oracle_user and settings.oracle_password and settings.oracle_dsn:
        oracle_client = OracleClient(settings=settings)

    app_context = AppContext(settings=settings, oracle_client=oracle_client)
    return {
        "context": app_context,
        "redis": build_redis_client(settings),
    }
