from __future__ import annotations

import html
import json
from urllib.parse import quote

from fastapi import FastAPI

from app.models.bots import BotActionPreset


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


BOT_PAYLOAD_PRESETS: list[dict[str, str]] = [
    {
        "label": "Ping JSON",
        "method": "POST",
        "payload": '{"source":"{{source}}","event":"ping","bot":"{{bot_username}}","triggered_at":"{{triggered_at}}"}',
    },
    {
        "label": "Restart JSON",
        "method": "POST",
        "payload": '{"source":"{{source}}","event":"restart","bot":"{{bot_username}}","triggered_at":"{{triggered_at}}"}',
    },
    {
        "label": "Deploy JSON",
        "method": "POST",
        "payload": '{"source":"{{source}}","event":"deploy","bot":"{{bot_username}}","name":"{{display_name}}","triggered_at":"{{triggered_at}}"}',
    },
    {
        "label": "Health GET",
        "method": "GET",
        "payload": "",
    },
]


def _matches_filters(values: list[str], row_status: str, query: str, status_filter: str) -> bool:
    if status_filter != "ALL" and row_status.upper() != status_filter:
        return False
    if not query:
        return True
    haystack = " ".join(value.lower() for value in values if value)
    return query.lower() in haystack


async def load_entity_rows(app: FastAPI, section: str, query: str = "", status_filter: str = "ALL") -> list[dict[str, str]]:
    if section == "Channels":
        active = await app.state.entity_service.list_channels()
        pending = await app.state.entity_service.list_channels_by_status("PENDING")
        blocked = await app.state.entity_service.list_channels_by_status("BLOCKED")
        ignored = await app.state.entity_service.list_channels_by_status("IGNORED")
    else:
        active = await app.state.entity_service.list_groups()
        pending = await app.state.entity_service.list_groups_by_status("PENDING")
        blocked = await app.state.entity_service.list_groups_by_status("BLOCKED")
        ignored = await app.state.entity_service.list_groups_by_status("IGNORED")

    rows = []
    for item in pending + active + blocked + ignored:
        created = item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "-"
        row = {
            "id": str(item.id or ""),
            "section": section,
            "title": item.title or "-",
            "identifier": item.chat_identifier,
            "status": item.status,
            "created_at": created,
        }
        if _matches_filters(
            [row["title"], row["identifier"], row["status"]],
            row["status"],
            query,
            status_filter,
        ):
            rows.append(row)
    return rows[:24]


async def load_bot_rows(app: FastAPI, query: str = "", status_filter: str = "ALL") -> list[dict[str, str]]:
    records = await app.state.bot_service.list_bots()
    rows = []
    for item in records:
        checked = item.last_checked_at.strftime("%Y-%m-%d %H:%M") if item.last_checked_at else "-"
        row = {
            "id": str(item.id or ""),
            "label": item.display_name or item.bot_username,
            "username": item.bot_username,
            "status": item.status,
            "health_url": item.healthcheck_url or "",
            "action_url": item.action_url or "",
            "action_method": item.action_method or "POST",
            "last_checked": checked,
        }
        if _matches_filters(
            [row["label"], row["username"], row["status"]],
            row["status"],
            query,
            status_filter,
        ):
            rows.append(row)
    return rows[:24]


def render_entity_table(title: str, rows: list[dict[str, str]], query: str, status_filter: str, csrf_token: str) -> str:
    section_id = "managed-channels" if "Channel" in title else "managed-groups"
    if not rows:
        return f"<div id=\"{section_id}\" class=\"card\"><h3>{title}</h3><p>No items found.</p></div>"

    body_rows = []
    for item in rows:
        status_class = {
            "PENDING": "status-pending",
            "ACTIVE": "status-active",
            "BLOCKED": "status-failed",
            "IGNORED": "status-muted",
        }.get(item["status"], "status-pending")
        action_buttons = render_entity_actions(item, query, status_filter, csrf_token)
        body_rows.append(
            f"""
            <tr>
              <td><a href="/dashboard/entity/{item['section'].lower()}/{item['id']}">{_e(item['title'])}</a></td>
              <td><code>{_e(item['identifier'])}</code></td>
              <td><span class="{status_class}">{_e(item['status'])}</span></td>
              <td>{_e(item['created_at'])}</td>
              <td>{action_buttons}</td>
            </tr>
            """
        )
    return f"""
    <div id="{section_id}" class="card wide">
      <h3>{title}</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Identifier</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {"".join(body_rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


def render_entity_actions(item: dict[str, str], query: str, status_filter: str, csrf_token: str) -> str:
    section = item["section"]
    entity_id = item["id"]
    status = item["status"]
    actions: list[tuple[str, str]] = []

    if status == "PENDING":
        actions = [("Allow", "ACTIVE"), ("Ignore", "IGNORED"), ("Block", "BLOCKED")]
    elif status == "ACTIVE":
        actions = [("Block", "BLOCKED")]
    elif status in {"BLOCKED", "IGNORED"}:
        actions = [("Activate", "ACTIVE")]

    if not actions:
        return "<span class=\"muted\">No actions</span>"

    parts = []
    for label, target_status in actions:
        parts.append(
            f"""
              <form method="post" action="/dashboard/entities/status">
                <input type="hidden" name="section" value="{section}" />
                <input type="hidden" name="entity_id" value="{entity_id}" />
                <input type="hidden" name="target_status" value="{target_status}" />
                <input type="hidden" name="csrf_token" value="{csrf_token}" />
                <input type="hidden" name="next_url" value="" />
                <input type="hidden" name="q" value="{_e(query)}" />
                <input type="hidden" name="status" value="{_e(status_filter)}" />
                <button type="submit">{label}</button>
            </form>
            """
        )
    return f"<div class=\"inline-actions\">{''.join(parts)}</div>"


def render_bot_table(title: str, rows: list[dict[str, str]], query: str, status_filter: str, csrf_token: str) -> str:
    section_id = "managed-bots"
    if not rows:
        return f"<div id=\"{section_id}\" class=\"card\"><h3>{title}</h3><p>No managed bots found for this filter.</p></div>"

    body_rows = []
    for item in rows:
        status_class = "status-active" if item["status"] == "ONLINE" else "status-pending"
        action_button = (
            f"""
            <form method="post" action="/dashboard/bots/action">
              <input type="hidden" name="bot_id" value="{item['id']}" />
              <input type="hidden" name="csrf_token" value="{csrf_token}" />
              <input type="hidden" name="q" value="{_e(query)}" />
              <input type="hidden" name="status" value="{_e(status_filter)}" />
              <button type="submit">Run Action</button>
            </form>
            """
            if item["action_url"]
            else "<span class=\"muted\">No action URL</span>"
        )
        body_rows.append(
            f"""
            <tr>
              <td><a href="/dashboard/bot/{item['id']}">{_e(item['label'])}</a></td>
              <td><code>{_e(item['username'])}</code></td>
              <td><span class="{status_class}">{_e(item['status'])}</span></td>
              <td>{_e(item['last_checked'])}</td>
              <td>
                <div class="inline-actions">
                  <form method="post" action="/dashboard/bots/refresh-one">
                    <input type="hidden" name="bot_id" value="{item['id']}" />
                    <input type="hidden" name="csrf_token" value="{csrf_token}" />
                    <input type="hidden" name="q" value="{_e(query)}" />
                    <input type="hidden" name="status" value="{_e(status_filter)}" />
                    <button type="submit">Refresh</button>
                  </form>
                  {action_button}
                </div>
              </td>
            </tr>
            """
        )
    return f"""
    <div id="{section_id}" class="card wide">
      <h3>{title}</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Username</th>
              <th>Status</th>
              <th>Last Checked</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {"".join(body_rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


def bot_detail_page(
    user_id: int,
    roles: list[str],
    record,
    activity_lines: list[str],
    diagnostics_lines: list[str],
    csrf_token: str,
    action_preview: dict[str, str] | None,
    custom_presets: list[BotActionPreset],
    notice: str = "",
    error: str = "",
) -> str:
    activity_html = "<br/>".join(_e(line) for line in activity_lines) if activity_lines else "No recent bot activity yet."
    diagnostics_html = "<br/>".join(_e(line) for line in diagnostics_lines) if diagnostics_lines else "No recent bot action diagnostics yet."
    status_class = "status-active" if record.status == "ONLINE" else "status-pending"
    checked = record.last_checked_at.strftime("%Y-%m-%d %H:%M") if record.last_checked_at else "-"
    preview_html = (
        f"""
        <p><strong>Method:</strong> {_e(action_preview['method'])}</p>
        <p><strong>Content-Type:</strong> {_e(action_preview['content_type'])}</p>
        <p><strong>Auth Header:</strong> {_e(action_preview['auth_header'])}</p>
        <p><strong>Auth Secret:</strong> {_e(action_preview['auth_secret'])}</p>
        <p><strong>Rendered At:</strong> {_e(action_preview['triggered_at'])}</p>
        <pre>{_e(action_preview['body'])}</pre>
        """
        if action_preview
        else "<p>No action preview available.</p>"
    )
    preset_buttons = "".join(
        f"""
        <button
          type="button"
          onclick="applyPreset('{_e(item['method'])}','{_e(item['payload'])}')"
        >{_e(item['label'])}</button>
        """
        for item in BOT_PAYLOAD_PRESETS
    )
    custom_preset_buttons = "".join(
        f"""
        <button
          type="button"
          onclick="applyPreset('{_e(item.method)}','{_e(item.payload)}')"
        >{_e(item.label)}</button>
        """
        for item in custom_presets
    )
    custom_presets_json = _e(
        json.dumps(
            [{"label": item.label, "method": item.method, "payload": item.payload} for item in custom_presets],
            ensure_ascii=True,
            indent=2,
        )
        if custom_presets
        else ""
    )
    banner_html = ""
    if notice:
        banner_html = f'<div class="card wide" style="background:#dcfce7;color:#166534;"><strong>{_e(notice)}</strong></div>'
    elif error:
        banner_html = f'<div class="card wide" style="background:#fee2e2;color:#991b1b;"><strong>{_e(error)}</strong></div>'
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Bot Detail</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; padding: 24px; color: #111827; }}
    .top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 18px; }}
    .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 12px 28px rgba(0,0,0,.06); }}
    .card.wide {{ grid-column: 1 / -1; }}
    .status-active, .status-pending {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .status-active {{ background: #dcfce7; color: #166534; }}
    .status-pending {{ background: #ffedd5; color: #9a3412; }}
    .inline-actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .stack {{ display: grid; gap: 12px; }}
    .preset-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
    form {{ margin: 0; }}
    input, select, textarea, button {{ padding: 10px 12px; border-radius: 10px; border: 1px solid #cbd5e1; }}
    button {{ background: #111827; color: white; border: none; cursor: pointer; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 6px; }}
    pre {{ white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="top">
    <div>
      <h2>Bot Detail</h2>
      <div>User: {_e(user_id)} | Roles: {_e(", ".join(roles))}</div>
    </div>
    <a href="/dashboard">Back to dashboard</a>
  </div>
  <div class="grid">
    {banner_html}
    <div class="card">
      <h3>Overview</h3>
      <p><strong>Name:</strong> {_e(record.display_name or '-')}</p>
      <p><strong>Username:</strong> <code>{_e(record.bot_username)}</code></p>
      <p><strong>Status:</strong> <span class="{status_class}">{_e(record.status)}</span></p>
      <p><strong>Last checked:</strong> {_e(checked)}</p>
    </div>
    <div class="card">
      <h3>Quick Actions</h3>
      <div class="inline-actions">
        <form method="post" action="/dashboard/bots/refresh-one">
          <input type="hidden" name="bot_id" value="{record.id}" />
          <input type="hidden" name="csrf_token" value="{csrf_token}" />
          <button type="submit">Refresh</button>
        </form>
        <form method="post" action="/dashboard/bots/action">
          <input type="hidden" name="bot_id" value="{record.id}" />
          <input type="hidden" name="csrf_token" value="{csrf_token}" />
          <button type="submit">Run Action</button>
        </form>
      </div>
    </div>
    <div class="card wide">
      <h3>Action Preview</h3>
      {preview_html}
    </div>
    <div class="card wide">
      <h3>Action Diagnostics</h3>
      <pre>{diagnostics_html}</pre>
    </div>
    <div class="card wide">
      <h3>Edit Config</h3>
      <form method="post" action="/dashboard/bots/update" class="stack">
        <input type="hidden" name="bot_id" value="{record.id}" />
        <input type="hidden" name="bot_username" value="{_e(record.bot_username)}" />
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <div class="preset-bar">
          {preset_buttons}
        </div>
        <div class="preset-bar">
          {custom_preset_buttons or '<span class="muted">No custom presets saved yet.</span>'}
        </div>
        <input type="text" name="display_name" value="{_e(record.display_name or '')}" placeholder="Display name" />
        <input type="text" name="healthcheck_url" value="{_e(record.healthcheck_url or '')}" placeholder="Healthcheck URL" />
        <input type="text" name="action_url" value="{_e(record.action_url or '')}" placeholder="Action URL" />
        <select name="action_method" id="action-method-field">
          <option value="GET" {'selected' if (record.action_method or 'POST') == 'GET' else ''}>GET</option>
          <option value="POST" {'selected' if (record.action_method or 'POST') == 'POST' else ''}>POST</option>
          <option value="PUT" {'selected' if (record.action_method or 'POST') == 'PUT' else ''}>PUT</option>
          <option value="PATCH" {'selected' if (record.action_method or 'POST') == 'PATCH' else ''}>PATCH</option>
          <option value="DELETE" {'selected' if (record.action_method or 'POST') == 'DELETE' else ''}>DELETE</option>
        </select>
        <textarea name="action_payload_template" id="action-payload-field" rows="5" placeholder='Payload template'>{_e(record.action_payload_template or '')}</textarea>
        <input type="text" name="action_auth_header" value="{_e(record.action_auth_header or '')}" placeholder="Action auth header" />
        <input type="text" name="action_secret" value="{_e(record.action_secret or '')}" placeholder="Action secret" />
        <textarea name="action_presets_json" rows="7" placeholder='Custom presets JSON: [{"label":"My Preset","method":"POST","payload":"{...}"}]'>{custom_presets_json}</textarea>
        <textarea name="notes" rows="4" placeholder="Notes">{_e(record.notes or '')}</textarea>
        <div class="inline-actions">
          <button type="submit">Save Bot Config</button>
          <button type="submit" formaction="/dashboard/bots/test-action">Test Action Without Saving</button>
        </div>
      </form>
    </div>
    <div class="card wide">
      <h3>Recent Activity</h3>
      <pre>{activity_html}</pre>
    </div>
  </div>
  <script>
    function applyPreset(method, payload) {{
      const methodField = document.getElementById('action-method-field');
      const payloadField = document.getElementById('action-payload-field');
      if (methodField) methodField.value = method;
      if (payloadField) payloadField.value = payload;
    }}
  </script>
</body>
</html>
"""


def entity_detail_page(
    user_id: int,
    roles: list[str],
    section: str,
    record,
    activity_lines: list[str],
    csrf_token: str,
    sensitive_mode: bool,
) -> str:
    filter_link = f"/dashboard?q={record.chat_identifier}&status=ALL"
    action_buttons = render_entity_detail_actions(section, record, csrf_token, sensitive_mode)
    activity_html = "<br/>".join(_e(line) for line in activity_lines) if activity_lines else "No recent entity activity yet."
    status_class = {
        "ACTIVE": "status-active",
        "PENDING": "status-pending",
        "BLOCKED": "status-failed",
        "FAILED": "status-failed",
        "IGNORED": "status-muted",
        "REMOVED": "status-muted",
        "CANCELED": "status-muted",
        "SENT": "status-active",
    }.get(record.status, "status-pending")
    sensitive_mode_html = (
        "<span class=\"status-active\">Unlocked</span>"
        if sensitive_mode
        else "<span class=\"status-pending\">Locked for block actions</span>"
    )
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{section[:-1]} Detail</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; padding: 24px; color: #111827; }}
    .top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 18px; }}
    .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 12px 28px rgba(0,0,0,.06); }}
    .card.wide {{ grid-column: 1 / -1; }}
    .status-active, .status-pending, .status-failed {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .status-active {{ background: #dcfce7; color: #166534; }}
    .status-pending {{ background: #ffedd5; color: #9a3412; }}
    .status-failed {{ background: #fee2e2; color: #991b1b; }}
    .status-muted {{ background: #e5e7eb; color: #475569; display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .inline-actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    form {{ margin: 0; }}
    button {{ padding: 10px 12px; border-radius: 10px; border: none; background: #111827; color: white; cursor: pointer; }}
    .danger {{ background: #991b1b; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 6px; }}
    pre {{ white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="top">
    <div>
      <h2>{section[:-1]} Detail</h2>
      <div>User: {_e(user_id)} | Roles: {_e(", ".join(roles))}</div>
    </div>
    <a href="/dashboard">Back to dashboard</a>
  </div>
  <div class="grid">
    <div class="card">
      <h3>Overview</h3>
      <p><strong>Title:</strong> {_e(record.title or '-')}</p>
      <p><strong>Identifier:</strong> <code>{_e(record.chat_identifier)}</code></p>
      <p><strong>Status:</strong> <span class="{status_class}">{_e(record.status)}</span></p>
      <p><strong>Added by:</strong> {_e(record.added_by_user_id or '-')}</p>
      <p><strong>Created:</strong> {_e(record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else '-')}</p>
    </div>
    <div class="card">
      <h3>Quick Links</h3>
      <p><a href="/dashboard">Open full dashboard</a></p>
      <p><a href="{filter_link}">Filter this item in dashboard</a></p>
      <p>Sensitive mode: {sensitive_mode_html}</p>
      <p><a href="/dashboard/reauth?next=/dashboard/entity/{section.lower()}/{record.id}">Unlock sensitive mode</a></p>
    </div>
    <div class="card">
      <h3>Quick Actions</h3>
      {action_buttons}
    </div>
    <div class="card wide">
      <h3>Recent Activity</h3>
      <pre>{activity_html}</pre>
    </div>
  </div>
</body>
</html>
"""


def render_entity_detail_actions(section: str, record, csrf_token: str, sensitive_mode: bool) -> str:
    actions: list[tuple[str, str, bool]] = []
    if record.status == "PENDING":
        actions = [("Allow", "ACTIVE", False), ("Ignore", "IGNORED", False), ("Block", "BLOCKED", True)]
    elif record.status == "ACTIVE":
        actions = [("Block", "BLOCKED", True)]
    elif record.status in {"BLOCKED", "IGNORED", "REMOVED"}:
        actions = [("Activate", "ACTIVE", False)]

    if not actions:
        return "<p>No quick actions available for this item.</p>"

    return_url = f"/dashboard/entity/{section.lower()}/{record.id}"
    parts: list[str] = []
    for label, target_status, is_danger in actions:
        button_class = "danger" if is_danger else ""
        if is_danger and not sensitive_mode:
            parts.append(
                f'<a href="/dashboard/reauth?next={quote(return_url, safe="/?=&")}" class="danger" '
                'style="display:inline-block;padding:10px 12px;border-radius:10px;color:white;text-decoration:none;background:#991b1b;">'
                f"{label}</a>"
            )
            continue
        parts.append(
            f"""
            <form method="post" action="/dashboard/entities/status">
              <input type="hidden" name="section" value="{section}" />
              <input type="hidden" name="entity_id" value="{record.id}" />
              <input type="hidden" name="target_status" value="{target_status}" />
              <input type="hidden" name="csrf_token" value="{csrf_token}" />
              <input type="hidden" name="next_url" value="{return_url}" />
              <input type="hidden" name="q" value="{record.chat_identifier}" />
              <input type="hidden" name="status" value="ALL" />
              <button class="{button_class}" type="submit">{label}</button>
            </form>
            """
        )
    return f'<div class="inline-actions">{"".join(parts)}</div>'
