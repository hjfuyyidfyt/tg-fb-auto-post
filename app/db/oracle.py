from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock

import oracledb

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OracleClient:
    settings: Settings
    _pool: oracledb.ConnectionPool | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def _build_connect_params(self) -> dict:
        params: dict = {
            "user": self.settings.oracle_user,
            "password": self.settings.oracle_password,
            "dsn": self.settings.oracle_dsn,
        }
        if self.settings.oracle_wallet_dir:
            params["config_dir"] = self.settings.oracle_wallet_dir
            params["wallet_location"] = self.settings.oracle_wallet_dir
            params["wallet_password"] = self.settings.oracle_password
        return params

    def _get_pool(self) -> oracledb.ConnectionPool:
        if self._pool is not None:
            return self._pool
        with self._lock:
            if self._pool is not None:
                return self._pool
            params = self._build_connect_params()
            params.update({
                "min": 2,
                "max": 8,
                "increment": 1,
                "ping_interval": 60,
                "timeout": 300,
                "getmode": oracledb.POOL_GETMODE_WAIT,
            })
            self._pool = oracledb.create_pool(**params)
            return self._pool

    def connect(self) -> oracledb.Connection:
        try:
            return self._get_pool().acquire()
        except (oracledb.InterfaceError, oracledb.DatabaseError):
            # Pool connection failed, reset pool and try direct connection
            logger.warning("Pool acquire failed, creating direct connection")
            self._reset_pool()
            return oracledb.connect(**self._build_connect_params())

    def _reset_pool(self) -> None:
        with self._lock:
            if self._pool is not None:
                try:
                    self._pool.close(force=True)
                except Exception:
                    pass
                self._pool = None

    def close(self) -> None:
        self._reset_pool()
