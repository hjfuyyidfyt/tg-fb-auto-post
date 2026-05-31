from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.runtime import AppContext
from app.models.bots import BotActionPreset, ManagedBotRecord
from app.repositories.bots import ManagedBotRepository
from app.services.bot_action_utils import (
    SUPPORTED_ACTION_METHODS,
    normalize_action_method,
    normalize_action_presets_json,
    parse_action_presets,
    parse_bot_input,
)


@dataclass(slots=True)
class PendingBotAction:
    action: str


class ManagedBotService:
    SUPPORTED_ACTION_METHODS = SUPPORTED_ACTION_METHODS
    MAX_ACTION_RESPONSE_CHARS = 240

    def __init__(self, app_context: AppContext, redis_client: object | None = None) -> None:
        self.app_context = app_context
        self.redis_client = redis_client

    async def set_pending_add(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        payload = json.dumps(asdict(PendingBotAction(action="add")))
        await asyncio.to_thread(self.redis_client.setex, self._pending_key(telegram_user_id), 900, payload)

    async def pop_pending_action(self, telegram_user_id: int) -> PendingBotAction | None:
        if not self.redis_client:
            return None
        key = self._pending_key(telegram_user_id)
        payload = await asyncio.to_thread(self.redis_client.get, key)
        if not payload:
            return None
        await asyncio.to_thread(self.redis_client.delete, key)
        return PendingBotAction(**json.loads(payload))

    async def get_pending_action(self, telegram_user_id: int) -> PendingBotAction | None:
        if not self.redis_client:
            return None
        payload = await asyncio.to_thread(self.redis_client.get, self._pending_key(telegram_user_id))
        if not payload:
            return None
        return PendingBotAction(**json.loads(payload))

    async def clear_pending_action(self, telegram_user_id: int) -> None:
        if not self.redis_client:
            return
        await asyncio.to_thread(self.redis_client.delete, self._pending_key(telegram_user_id))

    async def add_bot(
        self,
        bot_username: str,
        display_name: str | None,
        healthcheck_url: str | None,
        action_url: str | None,
        action_method: str | None,
        action_payload_template: str | None,
        action_presets_json: str | None,
        action_auth_header: str | None,
        action_secret: str | None,
        notes: str | None,
        created_by_user_id: int | None,
    ) -> ManagedBotRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ManagedBotRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.add_bot,
            self.normalize_bot_username(bot_username),
            display_name,
            healthcheck_url,
            action_url,
            self.normalize_action_method(action_method),
            action_payload_template,
            self.normalize_action_presets_json(action_presets_json),
            action_auth_header,
            action_secret,
            notes,
            created_by_user_id,
        )

    async def list_bots(self) -> list[ManagedBotRecord]:
        if not self.app_context.oracle_client:
            return []
        repository = ManagedBotRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.list_bots)

    async def get_bot(self, bot_id: int) -> ManagedBotRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ManagedBotRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.get_by_id, bot_id)

    async def update_bot(
        self,
        bot_id: int,
        display_name: str | None,
        healthcheck_url: str | None,
        action_url: str | None,
        action_method: str | None,
        action_payload_template: str | None,
        action_presets_json: str | None,
        action_auth_header: str | None,
        action_secret: str | None,
        notes: str | None,
    ) -> ManagedBotRecord | None:
        if not self.app_context.oracle_client:
            return None
        repository = ManagedBotRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(
            repository.update_bot,
            bot_id,
            display_name.strip() if display_name and display_name.strip() else None,
            healthcheck_url.strip() if healthcheck_url and healthcheck_url.strip() else None,
            action_url.strip() if action_url and action_url.strip() else None,
            self.normalize_action_method(action_method),
            action_payload_template.strip() if action_payload_template and action_payload_template.strip() else None,
            self.normalize_action_presets_json(action_presets_json),
            action_auth_header.strip() if action_auth_header and action_auth_header.strip() else None,
            action_secret.strip() if action_secret and action_secret.strip() else None,
            notes.strip() if notes and notes.strip() else None,
        )

    async def refresh_status(self, bot_id: int) -> ManagedBotRecord | None:
        record = await self.get_bot(bot_id)
        if not record:
            return None

        status = "UNKNOWN"
        if record.healthcheck_url:
            status = await asyncio.to_thread(self._probe_health, record.healthcheck_url)

        if not self.app_context.oracle_client:
            record.status = status
            return record

        repository = ManagedBotRepository(self.app_context.oracle_client)
        return await asyncio.to_thread(repository.update_status, bot_id, status)

    async def trigger_action(self, bot_id: int) -> tuple[ManagedBotRecord | None, str]:
        record = await self.get_bot(bot_id)
        if not record:
            return None, "Managed bot not found."
        if not record.action_url:
            return record, "No action URL is configured for this bot."
        result = await asyncio.to_thread(
            self._post_action,
            record,
        )
        return record, result

    async def preview_action(self, bot_id: int) -> tuple[ManagedBotRecord | None, dict[str, str] | None]:
        record = await self.get_bot(bot_id)
        if not record:
            return None, None
        preview = await asyncio.to_thread(self._build_action_preview, record)
        return record, preview

    async def test_action_config(
        self,
        *,
        bot_id: int,
        bot_username: str,
        display_name: str | None,
        action_url: str | None,
        action_method: str | None,
        action_payload_template: str | None,
        action_auth_header: str | None,
        action_secret: str | None,
    ) -> tuple[ManagedBotRecord | None, str]:
        record = await self.get_bot(bot_id)
        if not record:
            return None, "Managed bot not found."
        if not action_url or not action_url.strip():
            return record, "No action URL is configured for this test."

        test_record = ManagedBotRecord(
            id=record.id,
            bot_username=self.normalize_bot_username(bot_username),
            display_name=display_name.strip() if display_name and display_name.strip() else None,
            healthcheck_url=record.healthcheck_url,
            action_url=action_url.strip(),
            action_method=self.normalize_action_method(action_method),
            action_payload_template=action_payload_template.strip() if action_payload_template and action_payload_template.strip() else None,
            action_auth_header=action_auth_header.strip() if action_auth_header and action_auth_header.strip() else None,
            action_secret=action_secret.strip() if action_secret and action_secret.strip() else None,
            status=record.status,
            notes=record.notes,
            created_by_user_id=record.created_by_user_id,
            created_at=record.created_at,
            last_checked_at=record.last_checked_at,
        )
        result = await asyncio.to_thread(self._post_action, test_record)
        return test_record, result

    @staticmethod
    def normalize_bot_username(value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("@"):
            normalized = f"@{normalized}"
        return normalized

    @staticmethod
    def parse_bot_input(
        text: str,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None, str | None, str | None, str | None]:
        return parse_bot_input(text)

    @classmethod
    def normalize_action_method(cls, value: str | None) -> str:
        return normalize_action_method(value)

    @classmethod
    def normalize_action_presets_json(cls, value: str | None) -> str | None:
        return normalize_action_presets_json(value)

    @classmethod
    def parse_action_presets(cls, raw: str | None) -> list[BotActionPreset]:
        return parse_action_presets(raw)

    @staticmethod
    def _probe_health(url: str) -> str:
        request = Request(url, headers={"User-Agent": "everithing_manager/1.0"})
        try:
            with urlopen(request, timeout=5) as response:
                return "ONLINE" if 200 <= response.status < 400 else "DEGRADED"
        except URLError:
            return "OFFLINE"
        except Exception:
            return "OFFLINE"

    @staticmethod
    def _render_action_payload(record: ManagedBotRecord, triggered_at: str) -> tuple[bytes | None, str]:
        payload_context = {
            "source": "everithing_manager",
            "bot_username": record.bot_username,
            "display_name": record.display_name or "",
            "triggered_at": triggered_at,
        }
        if not record.action_payload_template:
            payload = json.dumps(payload_context).encode("utf-8")
            return payload, "application/json"

        rendered = record.action_payload_template
        for key, value in payload_context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

        try:
            payload = json.dumps(json.loads(rendered)).encode("utf-8")
            return payload, "application/json"
        except json.JSONDecodeError:
            return rendered.encode("utf-8"), "text/plain; charset=utf-8"

    @classmethod
    def _build_action_preview(cls, record: ManagedBotRecord) -> dict[str, str]:
        method = cls.normalize_action_method(record.action_method)
        triggered_at = datetime.now(timezone.utc).isoformat()
        payload = None
        content_type = "-"
        if method != "GET":
            payload, content_type = cls._render_action_payload(record, triggered_at)
        preview_body = "(GET request has no body)"
        if payload is not None:
            preview_body = payload.decode("utf-8", errors="replace")
        return {
            "method": method,
            "content_type": content_type,
            "triggered_at": triggered_at,
            "auth_header": record.action_auth_header or "-",
            "auth_secret": "SET" if record.action_secret else "-",
            "body": preview_body,
        }

    @classmethod
    def _summarize_response_body(cls, body: bytes | None) -> str:
        if not body:
            return "-"
        text = body.decode("utf-8", errors="replace").strip()
        if not text:
            return "-"
        compact = " ".join(text.split())
        if len(compact) > cls.MAX_ACTION_RESPONSE_CHARS:
            return compact[: cls.MAX_ACTION_RESPONSE_CHARS - 3] + "..."
        return compact

    @classmethod
    def _post_action(cls, record: ManagedBotRecord) -> str:
        method = cls.normalize_action_method(record.action_method)
        triggered_at = datetime.now(timezone.utc).isoformat()
        headers = {
            "User-Agent": "everithing_manager/1.0",
        }
        payload = None
        if method != "GET":
            payload, content_type = cls._render_action_payload(record, triggered_at)
            headers["Content-Type"] = content_type
        if record.action_auth_header and record.action_secret:
            headers[record.action_auth_header] = record.action_secret
        request = Request(
            record.action_url,
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=8) as response:
                response_body = cls._summarize_response_body(response.read())
                return f"ACTION_OK:{method}:{response.status}|body={response_body}"
        except HTTPError as exc:
            response_body = cls._summarize_response_body(exc.read())
            return f"ACTION_FAILED:{method}:HTTP_{exc.code}|body={response_body}"
        except URLError:
            return f"ACTION_FAILED:{method}:OFFLINE"
        except Exception:
            return f"ACTION_FAILED:{method}:ERROR"

    @staticmethod
    def _pending_key(telegram_user_id: int) -> str:
        return f"em:bot_pending:{telegram_user_id}"
