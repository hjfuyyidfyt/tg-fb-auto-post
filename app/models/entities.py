from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ManagedEntityRecord:
    id: int | None
    chat_identifier: str
    title: str | None
    added_by_user_id: int | None
    status: str
    created_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    @property
    def is_pending(self) -> bool:
        return self.status == "PENDING"
