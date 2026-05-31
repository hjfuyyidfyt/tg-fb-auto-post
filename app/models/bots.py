from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class BotActionPreset:
    label: str
    method: str
    payload: str


@dataclass(slots=True)
class ManagedBotRecord:
    id: int | None
    bot_username: str
    display_name: str | None
    healthcheck_url: str | None
    action_url: str | None
    action_method: str | None
    action_payload_template: str | None
    action_presets_json: str | None
    action_auth_header: str | None
    action_secret: str | None
    status: str
    notes: str | None
    created_by_user_id: int | None
    created_at: datetime | None = None
    last_checked_at: datetime | None = None
