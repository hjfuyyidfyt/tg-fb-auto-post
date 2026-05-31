from dataclasses import dataclass


@dataclass(slots=True)
class AuditLogRecord:
    actor_user_id: int | None
    action_key: str
    target_type: str | None = None
    target_id: str | None = None
    details: str | None = None
