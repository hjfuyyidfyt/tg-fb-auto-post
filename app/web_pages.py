from __future__ import annotations

import html
import json

from app.web_entities import render_bot_table, render_entity_table
from app.web_schedule import render_schedule_history_table, render_schedule_table


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def reauth_page(user_id: int, next_url: str, error: str | None = None) -> str:
    error_html = f"<p style='color:#b00020'>{_e(error)}</p>" if error else ""
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sensitive Mode Unlock</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f6f8; margin: 0; padding: 40px; }}
    .card {{ max-width: 460px; margin: 0 auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }}
    input, button {{ width: 100%; padding: 12px; margin-top: 10px; border-radius: 10px; border: 1px solid #d0d7de; }}
    button {{ background: #111827; color: white; border: none; cursor: pointer; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 6px; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Sensitive Mode Unlock</h2>
    <p>Use <code>/login_code</code> in Telegram and enter the fresh code here. Sensitive actions stay unlocked for 10 minutes.</p>
      <p>Telegram ID: <code>{_e(user_id)}</code></p>
      {error_html}
      <form method="post" action="/dashboard/reauth">
        <input type="hidden" name="next_url" value="{_e(next_url)}" />
        <input type="text" name="code" placeholder="6-digit login code" required />
        <button type="submit">Unlock Sensitive Mode</button>
      </form>
      <p><a href="{_e(next_url)}">Back to dashboard</a></p>
  </div>
</body>
</html>
"""


def login_page(error: str | None = None) -> str:
    error_html = f"<p style='color:#b00020'>{_e(error)}</p>" if error else ""
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>everithing_manager login</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f6f8; margin: 0; padding: 40px; }}
    .card {{ max-width: 420px; margin: 0 auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }}
    input, button {{ width: 100%; padding: 12px; margin-top: 10px; border-radius: 10px; border: 1px solid #d0d7de; }}
    button {{ background: #111827; color: white; border: none; cursor: pointer; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>everithing_manager</h2>
    <p>Use <code>/login_code</code> in Telegram, then sign in here.</p>
    {error_html}
    <form method="post" action="/login">
      <input type="number" name="telegram_user_id" placeholder="Telegram user ID" required />
      <input type="text" name="code" placeholder="6-digit login code" required />
      <button type="submit">Sign In</button>
    </form>
  </div>
</body>
</html>
"""


def dashboard_page(
    user_id: int,
    roles: list[str],
    daily: str,
    weekly: str,
    stats,
    templates,
    rules,
    bots,
    recent_activity,
    bot_action_history,
    automation_activity,
    automation_insights,
    ops_snapshot,
    action_center_links,
    automation_rule_history,
    alert_lines,
    delivery_results,
    active_channel_options,
    channel_rows,
    group_rows,
    schedule_rows,
    schedule_history_rows,
    query: str,
    status_filter: str,
    notice: str,
    error: str,
    csrf_token: str,
    sensitive_mode: bool,
) -> str:
    trigger_options = (
        ("PENDING_REVIEW", "Pending Review"),
        ("PENDING_CHANNELS", "Pending Channels"),
        ("PENDING_GROUPS", "Pending Groups"),
        ("FAILED_SCHEDULES", "Failed Schedules"),
        ("OFFLINE_BOTS", "Offline Bots"),
        ("DEGRADED_BOTS", "Degraded/Unknown Bots"),
        ("PAUSED_RECURRING_SCHEDULES", "Paused Recurring Schedules"),
    )
    template_options = "\n".join(
        f"<option value=\"{_e(item.key)}\">{_e(item.name)}</option>"
        for item in templates
    )
    if not template_options:
        template_options = "<option disabled>No templates</option>"

    rule_cards = []
    for item in rules:
        next_run = item.next_run_at.strftime("%Y-%m-%d %H:%M") if item.next_run_at else "Not scheduled"
        last_run = item.last_run_at.strftime("%Y-%m-%d %H:%M") if item.last_run_at else "Never"
        toggle_label = "Pause" if item.status == "ACTIVE" else "Activate"
        config_hint = ""
        custom_editor_html = ""
        if getattr(item, "config_json", None):
            config_hint = "<div class=\"muted\">Custom config attached</div>"
            try:
                config = json.loads(item.config_json)
            except json.JSONDecodeError:
                config = {}
            if isinstance(config, dict):
                config_kind = str(config.get("kind", "")).strip().upper()
                schedule_options = "\n".join(
                    (
                        f'<option value="{_e(value)}"'
                        + (" selected" if item.schedule_key == value else "")
                        + f">{_e(label)}</option>"
                    )
                    for value, label in (
                        ("DAILY", "Daily"),
                        ("WEEKLY", "Weekly"),
                        ("EVERY_2_HOURS", "Every 2 Hours"),
                        ("EVERY_6_HOURS", "Every 6 Hours"),
                    )
                )
                if config_kind == "CUSTOM_OWNER_ALERT":
                    custom_editor_html = f"""
                    <form method="post" action="/dashboard/automation/update-custom" class="stack" style="margin-top:12px;">
                      <input type="hidden" name="rule_id" value="{item.id}" />
                      <input type="hidden" name="rule_kind" value="{_e(config_kind)}" />
                      <input type="hidden" name="csrf_token" value="{csrf_token}" />
                      <input type="text" name="rule_name" value="{_e(item.template_name)}" placeholder="Rule name" />
                      <select name="schedule_key">{schedule_options}</select>
                      <input type="number" name="cooldown_minutes" min="0" value="{_e(config.get('cooldown_minutes', 0))}" placeholder="Cooldown minutes" />
                      <div class="inline-actions">
                        <input type="number" name="quiet_hours_start" min="0" max="23" value="{_e(config.get('quiet_hours_start', ''))}" placeholder="Quiet start hour" />
                        <input type="number" name="quiet_hours_end" min="0" max="23" value="{_e(config.get('quiet_hours_end', ''))}" placeholder="Quiet end hour" />
                      </div>
                      <div class="muted">Cooldown prevents repeat sends for N minutes after a successful run. Quiet hours use Bangladesh time (0-23). Example: start=23 end=8 blocks overnight.</div>
                      <textarea name="message_text" rows="4" placeholder="Message text" required>{_e(config.get("message_text", ""))}</textarea>
                      <button type="submit">Save Custom Rule</button>
                    </form>
                    """
                elif config_kind == "CUSTOM_CONDITION_ALERT":
                    selected_triggers = {
                        str(value).strip().upper()
                        for value in (config.get("trigger_keys") or [])
                        if str(value).strip()
                    }
                    if not selected_triggers:
                        legacy_trigger = str(config.get("trigger_key", "")).strip().upper()
                        if legacy_trigger:
                            selected_triggers = {legacy_trigger}
                    trigger_checks = "\n".join(
                        (
                            '<label class="check-item">'
                            f'<input type="checkbox" name="trigger_keys" value="{_e(value)}"'
                            + (" checked" if value in selected_triggers else "")
                            + f' /> <span>{_e(label)}</span></label>'
                        )
                        for value, label in trigger_options
                    )
                    custom_editor_html = f"""
                    <form method="post" action="/dashboard/automation/update-custom" class="stack" style="margin-top:12px;">
                      <input type="hidden" name="rule_id" value="{item.id}" />
                      <input type="hidden" name="rule_kind" value="{_e(config_kind)}" />
                      <input type="hidden" name="csrf_token" value="{csrf_token}" />
                      <input type="text" name="rule_name" value="{_e(item.template_name)}" placeholder="Rule name" />
                      <div class="check-grid">{trigger_checks}</div>
                      <select name="schedule_key">{schedule_options}</select>
                      <input type="number" name="threshold" min="1" value="{_e(config.get('threshold', 1))}" />
                      <input type="number" name="cooldown_minutes" min="0" value="{_e(config.get('cooldown_minutes', 0))}" placeholder="Cooldown minutes" />
                      <div class="inline-actions">
                        <input type="number" name="quiet_hours_start" min="0" max="23" value="{_e(config.get('quiet_hours_start', ''))}" placeholder="Quiet start hour" />
                        <input type="number" name="quiet_hours_end" min="0" max="23" value="{_e(config.get('quiet_hours_end', ''))}" placeholder="Quiet end hour" />
                      </div>
                      <div class="muted">Cooldown prevents repeat sends for N minutes after a successful run. Quiet hours use Bangladesh time (0-23). Example: start=23 end=8 blocks overnight.</div>
                      <textarea name="message_text" rows="4" placeholder="Message text" required>{_e(config.get("message_text", ""))}</textarea>
                      <button type="submit">Save Conditional Rule</button>
                    </form>
                    """
        rule_history = automation_rule_history.get(str(item.id), [])
        rule_history_html = (
            "<div class=\"rule-history\"><strong>Recent history</strong><br/>"
            + "<br/>".join(_e(line) for line in rule_history)
            + "</div>"
            if rule_history
            else "<div class=\"rule-history muted\">No recent rule history yet.</div>"
        )
        rule_cards.append(
            f"""
            <div class="rule">
              <div><strong>{_e(item.template_name)}</strong></div>
              <div>Status: {_e(item.status)}</div>
              <div>Schedule: {_e(item.schedule_key)}</div>
              <div>Last run: {_e(last_run)}</div>
              <div>Next run: {_e(next_run)}</div>
              {config_hint}
              <div class="actions">
                <form method="post" action="/dashboard/automation/toggle">
                  <input type="hidden" name="rule_id" value="{item.id}" />
                  <input type="hidden" name="csrf_token" value="{csrf_token}" />
                  <button type="submit">{toggle_label}</button>
                </form>
                <form method="post" action="/dashboard/automation/duplicate">
                  <input type="hidden" name="rule_id" value="{item.id}" />
                  <input type="hidden" name="csrf_token" value="{csrf_token}" />
                  <button type="submit">Duplicate</button>
                </form>
                <form method="post" action="/dashboard/automation/run-now">
                  <input type="hidden" name="rule_id" value="{item.id}" />
                  <input type="hidden" name="csrf_token" value="{csrf_token}" />
                  <button type="submit">Run Now</button>
                </form>
                <form method="post" action="/dashboard/automation/delete">
                  <input type="hidden" name="rule_id" value="{item.id}" />
                  <input type="hidden" name="csrf_token" value="{csrf_token}" />
                  <button class="danger" type="submit">Delete</button>
                </form>
              </div>
              {custom_editor_html}
              {rule_history_html}
            </div>
            """
        )
    rules_html = "\n".join(rule_cards) if rule_cards else "<p>No automation rules yet.</p>"
    bots_html = render_bot_table("Managed Bots", bots, query, status_filter, csrf_token)
    activity_html = "<br/>".join(_e(line) for line in recent_activity) if recent_activity else "No recent audit activity."
    bot_action_history_html = "<br/>".join(_e(line) for line in bot_action_history) if bot_action_history else "No recent bot action history yet."
    automation_activity_html = "<br/>".join(_e(line) for line in automation_activity) if automation_activity else "No automation activity yet."
    automation_insights_html = "<br/>".join(_e(line) for line in automation_insights) if automation_insights else "No automation insights yet."
    ops_snapshot_html = "<br/>".join(_e(line) for line in ops_snapshot) if ops_snapshot else "No ops snapshot available yet."
    alerts_html = "<br/>".join(_e(f"- {item}") for item in alert_lines) if alert_lines else "No urgent alerts right now."
    delivery_results_html = "<br/>".join(_e(line) for line in delivery_results) if delivery_results else "No recent web delivery results yet."
    action_center_html = "".join(
        f'<a class="action-link action-{_e(item["kind"])}" href="{_e(item["href"])}">{_e(item["label"])}</a>'
        for item in action_center_links
    )
    channels_html = render_entity_table("Managed Channels", channel_rows, query, status_filter, csrf_token)
    groups_html = render_entity_table("Managed Groups", group_rows, query, status_filter, csrf_token)
    schedules_html = render_schedule_table("Scheduled Posts", schedule_rows, query, status_filter, csrf_token)
    schedule_history_html = render_schedule_history_table("Schedule History", schedule_history_rows)
    banner_html = ""
    if notice:
        banner_html = f'<div class="banner success">{_e(notice)}</div>'
    elif error:
        banner_html = f'<div class="banner error">{_e(error)}</div>'
    sensitive_mode_html = (
        "<span class=\"status-active\">Unlocked for destructive actions</span>"
        if sensitive_mode
        else "<span class=\"status-pending\">Locked</span>"
    )
    selected_all = "selected" if status_filter == "ALL" else ""
    selected_active = "selected" if status_filter == "ACTIVE" else ""
    selected_pending = "selected" if status_filter == "PENDING" else ""
    selected_failed = "selected" if status_filter == "FAILED" else ""
    selected_online = "selected" if status_filter == "ONLINE" else ""
    selected_blocked = "selected" if status_filter == "BLOCKED" else ""
    selected_ignored = "selected" if status_filter == "IGNORED" else ""
    filter_bar = f"""
    <div class="card wide">
      <h3>Search And Filter</h3>
      <form method="get" action="/dashboard" class="filter-bar">
        <input type="text" name="q" value="{_e(query)}" placeholder="Search title, identifier, status, message..." />
        <select name="status">
          <option value="ALL" {selected_all}>All statuses</option>
          <option value="ACTIVE" {selected_active}>Active</option>
          <option value="PENDING" {selected_pending}>Pending</option>
          <option value="FAILED" {selected_failed}>Failed</option>
          <option value="ONLINE" {selected_online}>Online</option>
          <option value="BLOCKED" {selected_blocked}>Blocked</option>
          <option value="IGNORED" {selected_ignored}>Ignored</option>
        </select>
        <button type="submit">Apply</button>
        <a class="clear-link" href="/dashboard">Clear</a>
      </form>
    </div>
    """
    export_bar = """
    <div class="card wide">
      <h3>Exports</h3>
      <div class="inline-actions">
        <a class="button-link" href="/dashboard/export/daily">Download Daily</a>
        <a class="button-link" href="/dashboard/export/weekly">Download Weekly</a>
        <a class="button-link" href="/dashboard/export/ops">Download Ops Export</a>
        <a class="button-link" href="/dashboard/export/schedule-history">Download Schedule History</a>
        <a class="button-link" href="/dashboard/export/channels-csv">Channels CSV</a>
        <a class="button-link" href="/dashboard/export/groups-csv">Groups CSV</a>
        <a class="button-link" href="/dashboard/export/bots-csv">Bots CSV</a>
        <a class="button-link" href="/dashboard/export/schedules-csv">Schedules CSV</a>
        <a class="button-link" href="/dashboard/export/schedule-history-csv">Schedule History CSV</a>
      </div>
    </div>
    """
    channel_option_tags = "\n".join(
        f'<option value="{_e(item["identifier"])}" data-title="{_e(item["title"])}">{_e(item["title"])} ({_e(item["identifier"])})</option>'
        for item in active_channel_options
    ) or "<option disabled>No ACTIVE channels found</option>"
    conditional_trigger_checks = "\n".join(
        (
            '<label class="check-item">'
            f'<input type="checkbox" name="trigger_keys" value="{_e(value)}"'
            + (" checked" if value == "PENDING_REVIEW" else "")
            + f' /> <span>{_e(label)}</span></label>'
        )
        for value, label in trigger_options
    )
    broadcast_target_checks = "\n".join(
        f"""
        <label class="check-item">
          <input type="checkbox" name="channel_identifiers" value="{_e(item["identifier"])}" />
          <span>{_e(item["title"])} ({_e(item["identifier"])})</span>
        </label>
        """
        for item in active_channel_options
    ) or "<p class=\"muted\">No ACTIVE channels found.</p>"
    broadcast_card = f"""
    <div class="card">
      <h3>Web Broadcast</h3>
      <p>Send one message to all ACTIVE channels or only selected channels from the dashboard.</p>
      <p>Sensitive mode required.</p>
      <form method="post" action="/dashboard/broadcast/send-all" class="stack" enctype="multipart/form-data">
        <textarea name="message_text" rows="6" placeholder="Broadcast message text or caption"></textarea>
        <input type="file" name="media_file" />
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit">Send To All ACTIVE Channels</button>
      </form>
      <div style="height:12px;"></div>
      <form method="post" action="/dashboard/broadcast/send-selected" class="stack" enctype="multipart/form-data">
        <div class="check-grid">
          {broadcast_target_checks}
        </div>
        <textarea name="message_text" rows="6" placeholder="Selective broadcast text or caption"></textarea>
        <input type="file" name="media_file" />
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit" {"disabled" if not active_channel_options else ""}>Send To Selected Channels</button>
      </form>
    </div>
    """
    schedule_card = f"""
    <div class="card">
      <h3>Web Schedule</h3>
      <p>Create a scheduled post for one ACTIVE channel from the dashboard.</p>
      <form method="post" action="/dashboard/schedule/create" class="stack" id="web-schedule-form" enctype="multipart/form-data">
        <select name="channel_identifier" id="schedule-channel-select" {"disabled" if not active_channel_options else ""}>
          {channel_option_tags}
        </select>
        <input type="hidden" name="channel_title" id="schedule-channel-title" value="{_e(active_channel_options[0]['title'] if active_channel_options else '')}" />
        <input type="datetime-local" name="scheduled_for" required />
        <textarea name="message_text" rows="5" placeholder="Scheduled message text or caption"></textarea>
        <input type="file" name="media_file" />
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit" {"disabled" if not active_channel_options else ""}>Create Schedule</button>
      </form>
    </div>
    """
    stat_cards = f"""
    <div class="stat-card">
      <div class="stat-value">{stats['active_channels']}</div>
      <div class="stat-label">Active Channels</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['active_groups']}</div>
      <div class="stat-label">Active Groups</div>
    </div>
    <div class="stat-card alert">
      <div class="stat-value">{stats['pending_channels'] + stats['pending_groups']}</div>
      <div class="stat-label">Pending Review</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['pending_schedules']}</div>
      <div class="stat-label">Pending Schedules</div>
    </div>
    <div class="stat-card alert">
      <div class="stat-value">{stats['failed_schedules']}</div>
      <div class="stat-label">Failed Schedules</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['active_rules']}</div>
      <div class="stat-label">Active Automations</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{stats['online_bots']}</div>
      <div class="stat-label">Online Bots</div>
    </div>
    """

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>everithing_manager dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; padding: 24px; color: #111827; }}
    .top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(150px,1fr)); gap: 14px; margin-bottom: 20px; }}
    .stat-card {{ background: white; border-radius: 16px; padding: 18px; box-shadow: 0 12px 28px rgba(0,0,0,.06); }}
    .stat-card.alert {{ background: #fff7ed; }}
    .stat-value {{ font-size: 28px; font-weight: 700; }}
    .stat-label {{ color: #475569; margin-top: 6px; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(320px,1fr)); gap: 18px; }}
    .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 12px 28px rgba(0,0,0,.06); }}
    .card.wide {{ grid-column: 1 / -1; }}
    .stack {{ display: grid; gap: 14px; }}
    .filter-bar {{ display: grid; grid-template-columns: minmax(240px,1fr) 180px 120px 80px; gap: 12px; align-items: center; }}
    .rule {{ border: 1px solid #dbe3ef; border-radius: 12px; padding: 14px; margin-top: 12px; }}
    .rule-history {{ margin-top: 12px; padding-top: 10px; border-top: 1px dashed #dbe3ef; font-size: 12px; color: #334155; line-height: 1.5; }}
    .actions {{ display: flex; gap: 10px; margin-top: 12px; }}
    .inline-actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #e5e7eb; }}
    th {{ color: #475569; font-weight: 600; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 6px; }}
    .status-active, .status-pending, .status-failed {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .status-active {{ background: #dcfce7; color: #166534; }}
    .status-pending {{ background: #ffedd5; color: #9a3412; }}
    .status-failed {{ background: #fee2e2; color: #991b1b; }}
    .status-muted {{ background: #e5e7eb; color: #475569; }}
    form {{ margin: 0; }}
    input, select, button, textarea {{ padding: 10px 12px; border-radius: 10px; border: 1px solid #cbd5e1; }}
    button {{ background: #111827; color: white; border: none; cursor: pointer; }}
    .danger {{ background: #991b1b; }}
    .clear-link {{ color: #334155; text-decoration: none; }}
    .button-link {{ display: inline-block; padding: 10px 12px; border-radius: 10px; background: #111827; color: white; text-decoration: none; }}
    .action-center {{ display: grid; gap: 10px; }}
    .action-link {{ display: inline-block; padding: 10px 12px; border-radius: 12px; text-decoration: none; font-weight: 600; }}
    .action-danger {{ background: #fee2e2; color: #991b1b; }}
    .action-warning {{ background: #ffedd5; color: #9a3412; }}
    .action-neutral {{ background: #e0f2fe; color: #075985; }}
    .action-safe {{ background: #dcfce7; color: #166534; }}
    .check-grid {{ display: grid; gap: 8px; max-height: 180px; overflow-y: auto; padding: 8px; border: 1px solid #e5e7eb; border-radius: 12px; }}
    .check-item {{ display: flex; gap: 8px; align-items: center; font-size: 14px; }}
    .banner {{ grid-column: 1 / -1; padding: 14px 16px; border-radius: 14px; font-weight: 600; }}
    .banner.success {{ background: #dcfce7; color: #166534; }}
    .banner.error {{ background: #fee2e2; color: #991b1b; }}
    .muted {{ color: #64748b; font-size: 12px; }}
    pre {{ white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="top">
    <div>
      <h2>everithing_manager dashboard</h2>
      <div>User: {_e(user_id)} | Roles: {_e(", ".join(roles))}</div>
    </div>
    <a href="/logout">Log out</a>
  </div>
    <div class="stats">
      {stat_cards}
    </div>
  <div class="grid">
    {banner_html}
    {filter_bar}
    {export_bar}
    <div class="card">
      <h3>Daily</h3>
      <pre>{daily}</pre>
    </div>
    <div class="card">
      <h3>Weekly</h3>
      <pre>{weekly}</pre>
    </div>
    <div class="card">
      <h3>Create Automation</h3>
      <form method="post" action="/dashboard/automation/create" class="stack">
        <select name="template_key">
          {template_options}
        </select>
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit">Create Or Refresh Rule</button>
      </form>
    </div>
    <div class="card">
      <h3>Custom Owner Alert</h3>
      <form method="post" action="/dashboard/automation/create-custom" class="stack">
        <input type="text" name="rule_name" placeholder="Rule name" />
        <select name="schedule_key">
          <option value="DAILY">Daily</option>
          <option value="WEEKLY">Weekly</option>
          <option value="EVERY_2_HOURS">Every 2 Hours</option>
          <option value="EVERY_6_HOURS">Every 6 Hours</option>
        </select>
        <input type="number" name="cooldown_minutes" min="0" value="0" placeholder="Cooldown minutes" />
        <div class="inline-actions">
          <input type="number" name="quiet_hours_start" min="0" max="23" placeholder="Quiet start hour" />
          <input type="number" name="quiet_hours_end" min="0" max="23" placeholder="Quiet end hour" />
        </div>
        <div class="muted">Cooldown prevents repeat sends for N minutes after success. Quiet hours use Bangladesh time (0-23). Example: 23 to 8 blocks overnight.</div>
        <textarea name="message_text" rows="5" placeholder="Message to send to owners" required></textarea>
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit">Create Custom Alert Rule</button>
      </form>
    </div>
    <div class="card">
      <h3>Conditional Alert Rule</h3>
      <form method="post" action="/dashboard/automation/create-condition" class="stack">
        <input type="text" name="rule_name" placeholder="Rule name" />
        <div class="check-grid">
          {conditional_trigger_checks}
        </div>
        <div class="muted">Choose one or multiple triggers. Rule fires when any selected trigger crosses the threshold.</div>
        <select name="schedule_key">
          <option value="EVERY_2_HOURS">Every 2 Hours</option>
          <option value="EVERY_6_HOURS">Every 6 Hours</option>
          <option value="DAILY">Daily</option>
          <option value="WEEKLY">Weekly</option>
        </select>
        <input type="number" name="threshold" min="1" value="1" />
        <input type="number" name="cooldown_minutes" min="0" value="0" placeholder="Cooldown minutes" />
        <div class="inline-actions">
          <input type="number" name="quiet_hours_start" min="0" max="23" placeholder="Quiet start hour" />
          <input type="number" name="quiet_hours_end" min="0" max="23" placeholder="Quiet end hour" />
        </div>
        <div class="muted">Cooldown prevents repeat sends for N minutes after success. Quiet hours use Bangladesh time (0-23). Example: 23 to 8 blocks overnight.</div>
        <textarea name="message_text" rows="5" placeholder="Use placeholders like {{trigger}}, {{count}}, {{threshold}}, {{details}}" required></textarea>
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <button type="submit">Create Conditional Rule</button>
      </form>
    </div>
    <div class="card">
      <h3>Sensitive Mode</h3>
      <p>{sensitive_mode_html}</p>
      <p>Needed for delete, block, and cancel actions.</p>
      <a href="/dashboard/reauth?next=/dashboard">Unlock With Fresh Code</a>
    </div>
    {broadcast_card}
    {schedule_card}
    <div id="automation-rules" class="card">
      <h3>Automation Rules</h3>
      {rules_html}
    </div>
    <div id="managed-bots-summary" class="card">
      <h3>Managed Bots Summary</h3>
      <form method="post" action="/dashboard/bots/refresh" style="margin-bottom:12px;">
        <input type="hidden" name="csrf_token" value="{csrf_token}" />
        <input type="hidden" name="q" value="{_e(query)}" />
        <input type="hidden" name="status" value="{_e(status_filter)}" />
        <button type="submit">Refresh Bot Statuses</button>
      </form>
      <p>Use the table below for per-bot refresh and action trigger.</p>
    </div>
    <div class="card">
      <h3>Bot Action History</h3>
      <pre>{bot_action_history_html}</pre>
    </div>
    <div class="card">
      <h3>Recent Activity</h3>
      <pre>{activity_html}</pre>
    </div>
    <div class="card">
      <h3>Alerts</h3>
      <pre>{alerts_html}</pre>
    </div>
    <div class="card">
      <h3>Ops Snapshot</h3>
      <pre>{ops_snapshot_html}</pre>
    </div>
    <div class="card">
      <h3>Action Center</h3>
      <div class="action-center">{action_center_html}</div>
    </div>
    <div class="card">
      <h3>Automation Insights</h3>
      <pre>{automation_insights_html}</pre>
    </div>
    <div class="card">
      <h3>Automation History</h3>
      <pre>{automation_activity_html}</pre>
    </div>
    <div class="card">
      <h3>Delivery Results</h3>
      <pre>{delivery_results_html}</pre>
    </div>
    {bots_html}
    {schedules_html}
    {schedule_history_html}
    {channels_html}
    {groups_html}
  </div>
</body>
</html>
"""
