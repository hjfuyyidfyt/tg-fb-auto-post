from __future__ import annotations

import json

from app.models.bots import BotActionPreset


SUPPORTED_ACTION_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def normalize_action_method(value: str | None) -> str:
    normalized = (value or "POST").strip().upper()
    return normalized if normalized in SUPPORTED_ACTION_METHODS else "POST"


def parse_bot_input(
    text: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None, str | None, str | None, str | None]:
    parts = [part.strip() for part in text.split("|")]
    if not parts or not parts[0]:
        return None, None, None, None, None, None, None, None, None
    bot_username = parts[0]
    display_name = parts[1] if len(parts) > 1 and parts[1] else None
    healthcheck_url = parts[2] if len(parts) > 2 and parts[2] else None
    action_url = parts[3] if len(parts) > 3 and parts[3] else None
    action_method = None
    action_payload_template = None
    action_auth_header = None
    action_secret = None
    notes = None

    remaining = parts[4:]
    if remaining:
        first = remaining[0].upper() if remaining[0] else ""
        if first in SUPPORTED_ACTION_METHODS:
            action_method = first
            remaining = remaining[1:]
            if remaining:
                action_payload_template = remaining[0] or None
            if len(remaining) > 1:
                action_auth_header = remaining[1] or None
            if len(remaining) > 2:
                action_secret = remaining[2] or None
            if len(remaining) > 3:
                notes = remaining[3] or None
        else:
            if len(remaining) == 1:
                notes = remaining[0] or None
            else:
                action_auth_header = remaining[0] or None
                action_secret = remaining[1] or None if len(remaining) > 1 else None
                notes = remaining[2] or None if len(remaining) > 2 else None

    return (
        bot_username,
        display_name,
        healthcheck_url,
        action_url,
        action_method,
        action_payload_template,
        action_auth_header,
        action_secret,
        notes,
    )


def normalize_action_presets_json(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    normalized: list[dict[str, str]] = []
    for item in data[:12]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        method = normalize_action_method(str(item.get("method", "")).strip() or "POST")
        payload = str(item.get("payload", ""))
        if not label:
            continue
        normalized.append({"label": label[:40], "method": method, "payload": payload})
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=True)


def parse_action_presets(raw: str | None) -> list[BotActionPreset]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    presets: list[BotActionPreset] = []
    if not isinstance(data, list):
        return presets
    for item in data[:12]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        presets.append(
            BotActionPreset(
                label=label[:40],
                method=normalize_action_method(str(item.get("method", "")).strip() or "POST"),
                payload=str(item.get("payload", "")),
            )
        )
    return presets
