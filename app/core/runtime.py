from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from app.db.oracle import OracleClient


@dataclass(slots=True)
class AppContext:
    settings: Settings
    oracle_client: "OracleClient | None" = None
    core_roles_ready: bool = False
