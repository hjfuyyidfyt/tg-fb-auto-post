from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ScheduledPostRecord:
    id: int | None
    channel_identifier: str
    channel_title: str | None
    message_text: str
    scheduled_for: datetime
    recurrence_key: str | None
    media_path: str | None
    media_name: str | None
    media_type: str | None
    status: str
    created_by_user_id: int | None
