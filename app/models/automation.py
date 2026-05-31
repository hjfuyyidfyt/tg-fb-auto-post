from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class AutomationRuleRecord:
    id: int | None
    template_key: str
    template_name: str
    schedule_key: str
    config_json: str | None
    status: str
    created_by_user_id: int | None
    created_at: datetime | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
