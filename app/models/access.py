from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class UserRecord:
    id: int | None
    telegram_user_id: int
    username: str | None
    display_name: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class RoleRecord:
    id: int | None
    role_key: str
    role_name: str


@dataclass(slots=True)
class UserRoleSummary:
    telegram_user_id: int
    username: str | None
    display_name: str | None
    role_keys: list[str]


@dataclass(slots=True)
class AccessProfile:
    user: UserRecord
    role_keys: set[str] = field(default_factory=set)

    @property
    def is_owner(self) -> bool:
        return "OWNER" in self.role_keys

    @property
    def is_admin(self) -> bool:
        return bool(
            self.role_keys
            & {"OWNER", "SUPER_ADMIN", "CHANNEL_MANAGER", "GROUP_MANAGER", "MODERATOR", "VIEWER"}
        )
