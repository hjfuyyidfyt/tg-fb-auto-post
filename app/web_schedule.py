from __future__ import annotations

from fastapi import FastAPI


def escape_html(value: object) -> str:
    import html

    return html.escape("" if value is None else str(value), quote=True)


async def load_schedule_rows(
    app: FastAPI,
    matches_filters,
    media_only_sentinel: str,
    query: str = "",
    status_filter: str = "ALL",
) -> list[dict[str, str]]:
    pending = await app.state.schedule_service.list_pending()
    paused = await app.state.schedule_service.list_paused()
    failed = await app.state.schedule_service.list_failed()
    rows = []
    for item in failed + paused + pending:
        when = item.scheduled_for.strftime("%Y-%m-%d %H:%M") if item.scheduled_for else "-"
        preview = (item.message_text or "").strip().replace("\n", " ")
        if preview == media_only_sentinel:
            preview = "[media only]"
        if len(preview) > 60:
            preview = preview[:57] + "..."
        row = {
            "id": str(item.id or ""),
            "channel": item.channel_title or item.channel_identifier,
            "identifier": item.channel_identifier,
            "status": item.status,
            "scheduled_for": when,
            "preview": preview or "-",
            "recurrence": item.recurrence_key or "",
            "media": item.media_name or "",
        }
        if matches_filters(
            [row["channel"], row["identifier"], row["status"], row["preview"], row["recurrence"], row["media"]],
            row["status"],
            query,
            status_filter,
        ):
            rows.append(row)
    return rows[:24]


async def load_schedule_history_rows(
    app: FastAPI,
    matches_filters,
    media_only_sentinel: str,
    query: str = "",
    status_filter: str = "ALL",
) -> list[dict[str, str]]:
    records = await app.state.schedule_service.list_recent_history(30)
    rows = []
    for item in records:
        when = item.scheduled_for.strftime("%Y-%m-%d %H:%M") if item.scheduled_for else "-"
        preview = (item.message_text or "").strip().replace("\n", " ")
        if preview == media_only_sentinel:
            preview = "[media only]"
        if len(preview) > 60:
            preview = preview[:57] + "..."
        row = {
            "id": str(item.id or ""),
            "channel": item.channel_title or item.channel_identifier,
            "identifier": item.channel_identifier,
            "status": item.status,
            "scheduled_for": when,
            "preview": preview or "-",
        }
        if matches_filters(
            [row["channel"], row["identifier"], row["status"], row["preview"]],
            row["status"],
            query,
            status_filter,
        ):
            rows.append(row)
    return rows[:24]


def render_schedule_table(title: str, rows: list[dict[str, str]], query: str, status_filter: str, csrf_token: str) -> str:
    section_id = "scheduled-posts"
    if not rows:
        return f"<div id=\"{section_id}\" class=\"card wide\"><h3>{title}</h3><p>No schedules found.</p></div>"

    body_rows = []
    for item in rows:
        status_class = (
            "status-failed" if item["status"] == "FAILED" else
            "status-muted" if item["status"] == "PAUSED" else
            "status-pending"
        )
        if item["status"] == "PENDING":
            parts = []
            if item.get("recurrence"):
                parts.append(render_schedule_action_button(item["id"], "PAUSED", "Pause", query, status_filter, csrf_token))
                parts.append(render_schedule_action_button(item["id"], "SKIP_NEXT", "Skip Next", query, status_filter, csrf_token))
            parts.append(render_schedule_action_button(item["id"], "CANCELED", "Cancel", query, status_filter, csrf_token, danger=True))
            actions_html = f"<div class=\"inline-actions\">{''.join(parts)}</div>"
        elif item["status"] == "PAUSED":
            actions_html = (
                f"<div class=\"inline-actions\">"
                f"{render_schedule_action_button(item['id'], 'PENDING', 'Resume', query, status_filter, csrf_token)}"
                f"{render_schedule_action_button(item['id'], 'CANCELED', 'Cancel', query, status_filter, csrf_token, danger=True)}"
                f"</div>"
            )
        elif item["status"] == "FAILED":
            actions_html = render_schedule_action_button(item["id"], "PENDING", "Retry", query, status_filter, csrf_token)
        else:
            actions_html = "<span class=\"muted\">No actions</span>"
        body_rows.append(
            f"""
            <tr>
              <td>{escape_html(item['channel'])}</td>
              <td><code>{escape_html(item['identifier'])}</code></td>
              <td><span class="{status_class}">{escape_html(item['status'])}</span></td>
              <td>{escape_html(item['scheduled_for'])}</td>
              <td>{escape_html(item['recurrence'] or '-')}</td>
              <td>{escape_html(item['preview'])}{' | media=' + escape_html(item['media']) if item['media'] else ''}</td>
              <td>{actions_html}</td>
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
              <th>Channel</th>
              <th>Identifier</th>
              <th>Status</th>
              <th>Scheduled For</th>
              <th>Repeat</th>
              <th>Message</th>
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


def render_schedule_history_table(title: str, rows: list[dict[str, str]]) -> str:
    section_id = "schedule-history"
    if not rows:
        return f"<div id=\"{section_id}\" class=\"card wide\"><h3>{title}</h3><p>No schedule history found.</p></div>"

    body_rows = []
    for item in rows:
        status_class = {
            "SENT": "status-active",
            "FAILED": "status-failed",
            "CANCELED": "status-muted",
        }.get(item["status"], "status-pending")
        body_rows.append(
            f"""
            <tr>
              <td>{escape_html(item['channel'])}</td>
              <td><code>{escape_html(item['identifier'])}</code></td>
              <td><span class="{status_class}">{escape_html(item['status'])}</span></td>
              <td>{escape_html(item['scheduled_for'])}</td>
              <td>{escape_html(item['preview'])}</td>
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
              <th>Channel</th>
              <th>Identifier</th>
              <th>Status</th>
              <th>Scheduled For</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {"".join(body_rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


def render_schedule_action_button(
    schedule_id: str,
    target_status: str,
    label: str,
    query: str,
    status_filter: str,
    csrf_token: str,
    danger: bool = False,
) -> str:
    button_class = "danger" if danger else ""
    return f"""
    <form method="post" action="/dashboard/schedules/status">
      <input type="hidden" name="schedule_id" value="{schedule_id}" />
      <input type="hidden" name="target_status" value="{target_status}" />
      <input type="hidden" name="csrf_token" value="{csrf_token}" />
      <input type="hidden" name="q" value="{escape_html(query)}" />
      <input type="hidden" name="status" value="{escape_html(status_filter)}" />
      <button class="{button_class}" type="submit">{label}</button>
    </form>
    """
