from __future__ import annotations

from pathlib import Path
import secrets
from datetime import timedelta, timezone
from urllib.parse import quote

from aiogram import Bot
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from itsdangerous import URLSafeSerializer

from app.core.config import load_settings
from app.repositories.access import AccessRepository
from app.services.automation import AutomationService
from app.services.automation_runner import AutomationRunner
from app.services.bots import ManagedBotService
from app.services.bootstrap import bootstrap_dependencies
from app.services.entities import ManagedEntityService
from app.services.login_codes import LoginCodeService
from app.services.reports import ReportService
from app.services.schedule import ScheduleService
from app.web_entities import (
    bot_detail_page,
    entity_detail_page,
    load_bot_rows,
    load_entity_rows,
)
from app.web_data import (
    build_export_payload,
    entity_target_type,
    load_active_channel_options,
    load_alert_lines,
    load_automation_rule_history,
    load_automation_insights,
    load_ops_snapshot,
    load_action_center_links,
    load_bot_action_history,
    load_bot_action_diagnostics,
    load_dashboard_stats,
    load_delivery_results,
    load_bot_detail_activity,
    load_entity_detail_activity,
    load_recent_activity,
    load_recent_automation_activity,
    matches_filters,
    record_audit_event,
)
from app.web_pages import dashboard_page, login_page, reauth_page
from app.web_runtime import (
    dashboard_redirect,
    has_sensitive_session,
    read_csrf_token,
    read_session_user_id,
    reauth_redirect_url,
    safe_next_url,
    send_web_content,
    store_schedule_media,
    validate_csrf,
    validate_upload,
)
from app.web_schedule import (
    load_schedule_history_rows,
    load_schedule_rows,
)
from app.web_validation import validate_automation_timing

MAX_WEB_UPLOAD_BYTES = 10 * 1024 * 1024
SCHEDULE_MEDIA_DIR = Path("/app/data/scheduled_media")
MEDIA_ONLY_SENTINEL = "[media-only]"


def build_app() -> FastAPI:
    settings = load_settings()
    dependencies = bootstrap_dependencies(settings)
    app = FastAPI(title="everithing_manager dashboard")

    redis_client = dependencies["redis"]
    app.state.settings = settings
    app.state.context = dependencies["context"]
    app.state.login_codes = LoginCodeService(redis_client=redis_client)
    app.state.report_service = ReportService(dependencies["context"], redis_client=redis_client)
    app.state.automation_service = AutomationService(dependencies["context"])
    app.state.bot_service = ManagedBotService(dependencies["context"], redis_client=redis_client)
    app.state.entity_service = ManagedEntityService(dependencies["context"], redis_client=redis_client)
    app.state.schedule_service = ScheduleService(dependencies["context"], redis_client=redis_client)
    app.state.bot_api = Bot(token=settings.bot_token) if settings.bot_token else None
    app.state.serializer = URLSafeSerializer(settings.dashboard_secret, salt="em-dashboard")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        if app.state.bot_api:
            await app.state.bot_api.session.close()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        user_id = read_session_user_id(request)
        if user_id is not None and _current_role_keys(app, user_id):
            return RedirectResponse(url="/dashboard", status_code=302)
        return HTMLResponse(login_page())

    @app.post("/login")
    async def login(request: Request, telegram_user_id: int = Form(...), code: str = Form(...)):
        if not await app.state.login_codes.validate_code(telegram_user_id, code):
            return HTMLResponse(login_page("Invalid or expired code."), status_code=400)

        role_keys = _current_role_keys(app, telegram_user_id)
        if not role_keys:
            return HTMLResponse(login_page("This account has no approved admin access."), status_code=403)

        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            "em_session",
            app.state.serializer.dumps(
                {
                    "telegram_user_id": telegram_user_id,
                    "csrf_token": secrets.token_urlsafe(24),
                }
            ),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=60 * 60 * 8,
            path="/",
        )
        return response

    @app.get("/logout")
    async def logout() -> RedirectResponse:
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("em_session")
        response.delete_cookie("em_sensitive")
        return response

    @app.get("/dashboard/reauth", response_class=HTMLResponse)
    async def reauth_page(request: Request) -> HTMLResponse:
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        next_url = safe_next_url(request.query_params.get("next"))
        return HTMLResponse(reauth_page(user_id, next_url))

    @app.post("/dashboard/reauth")
    async def reauth_submit(request: Request, code: str = Form(...), next_url: str = Form("/dashboard")):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        next_url = safe_next_url(next_url)
        if not await app.state.login_codes.validate_code(user_id, code):
            return HTMLResponse(reauth_page(user_id, next_url, "Invalid or expired code."), status_code=400)

        response = RedirectResponse(url=next_url or "/dashboard", status_code=302)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        response.set_cookie(
            "em_sensitive",
            app.state.serializer.dumps(
                {
                    "telegram_user_id": user_id,
                    "expires_at": expires_at.isoformat(),
                }
            ),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=60 * 10,
            path="/",
        )
        return response

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)

        role_keys = _current_role_keys(app, user_id)
        if not role_keys:
            response = RedirectResponse(url="/", status_code=302)
            response.delete_cookie("em_session")
            return response

        query = (request.query_params.get("q") or "").strip()
        status_filter = (request.query_params.get("status") or "ALL").strip().upper()
        notice = (request.query_params.get("notice") or "").strip()
        error = (request.query_params.get("error") or "").strip()
        csrf_token = read_csrf_token(request)
        sensitive_mode = has_sensitive_session(request)

        bundle = await app.state.report_service.build_reports()
        templates = app.state.automation_service.list_templates()
        rules = await app.state.automation_service.list_rules()
        bots = await load_bot_rows(app, query, status_filter)
        recent_activity = await load_recent_activity(app, limit=12)
        bot_action_history = await load_bot_action_history(app, limit=12)
        automation_activity = await load_recent_automation_activity(app, limit=12)
        automation_insights = await load_automation_insights(app, rules)
        ops_snapshot = await load_ops_snapshot(app, rules)
        action_center_links = await load_action_center_links(app, rules)
        automation_rule_history = await load_automation_rule_history(app, rules, limit_per_rule=4)
        alert_lines = await load_alert_lines(app, rules)
        delivery_results = await load_delivery_results(app, limit=12)
        stats = await load_dashboard_stats(app)
        active_channel_options = await load_active_channel_options(app)
        channel_rows = await load_entity_rows(app, "Channels", query, status_filter)
        group_rows = await load_entity_rows(app, "Groups", query, status_filter)
        schedule_rows = await load_schedule_rows(app, matches_filters, MEDIA_ONLY_SENTINEL, query, status_filter)
        schedule_history_rows = await load_schedule_history_rows(
            app,
            matches_filters,
            MEDIA_ONLY_SENTINEL,
            query,
            status_filter,
        )
        response = HTMLResponse(
            dashboard_page(
                user_id,
                sorted(role_keys),
                bundle.daily_text,
                bundle.weekly_text,
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
                query,
                status_filter,
                notice,
                error,
                csrf_token,
                sensitive_mode,
            )
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/dashboard/export/{export_key}")
    async def export_dashboard_data(request: Request, export_key: str):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)

        export_key = export_key.lower().strip()
        content, filename = await build_export_payload(app, export_key, MEDIA_ONLY_SENTINEL)
        if content is None or filename is None:
            return HTMLResponse("Unknown export target.", status_code=404)

        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/dashboard/bots/refresh")
    async def refresh_bots(
        request: Request,
        csrf_token: str = Form(...),
        q: str = Form(""),
        status: str = Form("ALL"),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        bots = await app.state.bot_service.list_bots()
        for item in bots[:15]:
            refreshed = await app.state.bot_service.refresh_status(item.id)
            if refreshed:
                await record_audit_event(
                    app,
                    actor_user_id=user_id,
                    action_key="WEB_REFRESH_MANAGED_BOT_STATUS",
                    target_type="BOT",
                    target_id=refreshed.bot_username,
                    details=refreshed.status,
                )
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="WEB_REFRESH_ALL_MANAGED_BOT_STATUSES",
            target_type="BOT",
            target_id="ALL",
            details=f"count={min(len(bots), 15)}",
        )
        return RedirectResponse(url=f"/dashboard?q={q}&status={status}", status_code=302)

    @app.post("/dashboard/bots/refresh-one")
    async def refresh_one_bot(
        request: Request,
        bot_id: int = Form(...),
        csrf_token: str = Form(...),
        q: str = Form(""),
        status: str = Form("ALL"),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        refreshed = await app.state.bot_service.refresh_status(bot_id)
        if refreshed:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_REFRESH_MANAGED_BOT_STATUS",
                target_type="BOT",
                target_id=refreshed.bot_username,
                details=refreshed.status,
            )
        return RedirectResponse(url=f"/dashboard?q={q}&status={status}", status_code=302)

    @app.post("/dashboard/bots/action")
    async def trigger_one_bot_action(
        request: Request,
        bot_id: int = Form(...),
        csrf_token: str = Form(...),
        q: str = Form(""),
        status: str = Form("ALL"),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        record, result = await app.state.bot_service.trigger_action(bot_id)
        if record:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_TRIGGER_MANAGED_BOT_ACTION",
                target_type="BOT",
                target_id=record.bot_username,
                details=result,
            )
        return RedirectResponse(url=f"/dashboard?q={q}&status={status}", status_code=302)

    @app.get("/dashboard/bot/{bot_id}", response_class=HTMLResponse)
    async def bot_detail(request: Request, bot_id: int) -> HTMLResponse:
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        role_keys = _current_role_keys(app, user_id)
        if not role_keys:
            response = RedirectResponse(url="/", status_code=302)
            response.delete_cookie("em_session")
            return response

        notice = (request.query_params.get("notice") or "").strip()
        error = (request.query_params.get("error") or "").strip()
        record = await app.state.bot_service.get_bot(bot_id)
        if not record:
            return HTMLResponse("Managed bot not found.", status_code=404)

        activity_lines = await load_bot_detail_activity(app, record.bot_username, limit=12)
        diagnostics_lines = await load_bot_action_diagnostics(app, record.bot_username, limit=10)
        _, action_preview = await app.state.bot_service.preview_action(bot_id)
        custom_presets = app.state.bot_service.parse_action_presets(record.action_presets_json)
        csrf_token = read_csrf_token(request)
        response = HTMLResponse(
            bot_detail_page(
                user_id=user_id,
                roles=sorted(role_keys),
                record=record,
                activity_lines=activity_lines,
                diagnostics_lines=diagnostics_lines,
                csrf_token=csrf_token,
                action_preview=action_preview,
                custom_presets=custom_presets,
                notice=notice,
                error=error,
            )
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.post("/dashboard/bots/update")
    async def update_bot_config(
        request: Request,
        bot_id: int = Form(...),
        bot_username: str = Form(""),
        display_name: str = Form(""),
        healthcheck_url: str = Form(""),
        action_url: str = Form(""),
        action_method: str = Form("POST"),
        action_payload_template: str = Form(""),
        action_presets_json: str = Form(""),
        action_auth_header: str = Form(""),
        action_secret: str = Form(""),
        notes: str = Form(""),
        csrf_token: str = Form(...),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        updated = await app.state.bot_service.update_bot(
            bot_id=bot_id,
            display_name=display_name,
            healthcheck_url=healthcheck_url,
            action_url=action_url,
            action_method=action_method,
            action_payload_template=action_payload_template,
            action_presets_json=action_presets_json,
            action_auth_header=action_auth_header,
            action_secret=action_secret,
            notes=notes,
        )
        if updated:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_UPDATE_MANAGED_BOT_CONFIG",
                target_type="BOT",
                target_id=updated.bot_username,
                details=f"method={updated.action_method or 'POST'}|health={'set' if updated.healthcheck_url else '-'}|action={'set' if updated.action_url else '-'}",
            )
        return RedirectResponse(url=f"/dashboard/bot/{bot_id}", status_code=302)

    @app.post("/dashboard/bots/test-action")
    async def test_bot_action(
        request: Request,
        bot_id: int = Form(...),
        bot_username: str = Form(""),
        display_name: str = Form(""),
        action_url: str = Form(""),
        action_method: str = Form("POST"),
        action_payload_template: str = Form(""),
        action_auth_header: str = Form(""),
        action_secret: str = Form(""),
        csrf_token: str = Form(...),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        record, result = await app.state.bot_service.test_action_config(
            bot_id=bot_id,
            bot_username=bot_username,
            display_name=display_name,
            action_url=action_url,
            action_method=action_method,
            action_payload_template=action_payload_template,
            action_auth_header=action_auth_header,
            action_secret=action_secret,
        )
        if record:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_TEST_MANAGED_BOT_ACTION",
                target_type="BOT",
                target_id=record.bot_username,
                details=result,
            )
            return RedirectResponse(
                url=f"/dashboard/bot/{bot_id}?notice={quote(result, safe='')}",
                status_code=302,
            )

        return RedirectResponse(
            url=f"/dashboard/bot/{bot_id}?error={quote(result, safe='')}",
            status_code=302,
        )

    @app.post("/dashboard/broadcast/send-all")
    async def dashboard_broadcast_send_all(
        request: Request,
        message_text: str = Form(...),
        csrf_token: str = Form(...),
        media_file: UploadFile | None = File(None),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not has_sensitive_session(request):
            return RedirectResponse(url=reauth_redirect_url(), status_code=302)
        if not app.state.bot_api:
            return HTMLResponse("Bot API is not configured.", status_code=500)

        message_text = (message_text or "").strip()
        if not message_text and not media_file:
            return HTMLResponse("Broadcast text or file is required.", status_code=400)
        if media_file:
            upload_error = await validate_upload(media_file, MAX_WEB_UPLOAD_BYTES)
            if upload_error:
                return dashboard_redirect(error=upload_error)

        channels = await app.state.entity_service.list_channels()
        success_count = 0
        failed_targets: list[str] = []
        for item in channels:
            try:
                await send_web_content(
                    app.state.bot_api,
                    item.chat_identifier,
                    message_text,
                    media_file,
                )
                success_count += 1
                await record_audit_event(
                    app,
                    actor_user_id=user_id,
                    action_key="WEB_BROADCAST_CHANNEL_MESSAGE",
                    target_type="CHANNEL",
                    target_id=item.chat_identifier,
                    details=f"title={item.title or '-'}|media={getattr(media_file, 'filename', '') or '-'}",
                )
            except Exception:
                failed_targets.append(item.title or item.chat_identifier)

        summary = f"WEB broadcast complete: {success_count}/{len(channels)}"
        if failed_targets:
            summary += " | failed=" + ", ".join(failed_targets[:10])
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="WEB_BROADCAST_ALL",
            target_type="BROADCAST",
            target_id="ALL_ACTIVE_CHANNELS",
            details=summary,
        )
        return dashboard_redirect(notice=summary)

    @app.post("/dashboard/broadcast/send-selected")
    async def dashboard_broadcast_send_selected(
        request: Request,
        channel_identifiers: list[str] = Form(...),
        message_text: str = Form(...),
        csrf_token: str = Form(...),
        media_file: UploadFile | None = File(None),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not has_sensitive_session(request):
            return RedirectResponse(url=reauth_redirect_url(), status_code=302)
        if not app.state.bot_api:
            return HTMLResponse("Bot API is not configured.", status_code=500)

        normalized_targets = sorted({item.strip() for item in channel_identifiers if item and item.strip()})
        message_text = (message_text or "").strip()
        if not normalized_targets:
            return HTMLResponse("Select at least one channel.", status_code=400)
        if not message_text and not media_file:
            return HTMLResponse("Broadcast text or file is required.", status_code=400)
        if media_file:
            upload_error = await validate_upload(media_file, MAX_WEB_UPLOAD_BYTES)
            if upload_error:
                return dashboard_redirect(error=upload_error)

        channels = await app.state.entity_service.list_channels()
        allowed_map = {item.chat_identifier: item for item in channels}
        targets = [allowed_map[item] for item in normalized_targets if item in allowed_map]
        if not targets:
            return HTMLResponse("No valid ACTIVE channels were selected.", status_code=400)

        success_count = 0
        failed_targets: list[str] = []
        for item in targets:
            try:
                await send_web_content(
                    app.state.bot_api,
                    item.chat_identifier,
                    message_text,
                    media_file,
                )
                success_count += 1
                await record_audit_event(
                    app,
                    actor_user_id=user_id,
                    action_key="WEB_BROADCAST_CHANNEL_MESSAGE",
                    target_type="CHANNEL",
                    target_id=item.chat_identifier,
                    details=f"title={item.title or '-'}|selected=1|media={getattr(media_file, 'filename', '') or '-'}",
                )
            except Exception:
                failed_targets.append(item.title or item.chat_identifier)

        summary = f"WEB selective broadcast complete: {success_count}/{len(targets)}"
        if failed_targets:
            summary += " | failed=" + ", ".join(failed_targets[:10])
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="WEB_BROADCAST_SELECTED",
            target_type="BROADCAST",
            target_id="SELECTED_ACTIVE_CHANNELS",
            details=summary,
        )
        return dashboard_redirect(notice=summary)

    @app.post("/dashboard/schedule/create")
    async def dashboard_schedule_create(
        request: Request,
        channel_identifier: str = Form(...),
        channel_title: str = Form(""),
        scheduled_for: str = Form(...),
        message_text: str = Form(...),
        csrf_token: str = Form(...),
        media_file: UploadFile | None = File(None),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        message_text = (message_text or "").strip()
        if not channel_identifier.strip():
            return HTMLResponse("Channel identifier is required.", status_code=400)
        if not message_text and not media_file:
            return HTMLResponse("Schedule message text or file is required.", status_code=400)
        if media_file:
            upload_error = await validate_upload(media_file, MAX_WEB_UPLOAD_BYTES)
            if upload_error:
                return dashboard_redirect(error=upload_error)
        active_channels = await app.state.entity_service.list_channels()
        channel_map = {item.chat_identifier: item for item in active_channels}
        selected_channel = channel_map.get(channel_identifier.strip())
        if not selected_channel:
            return dashboard_redirect(error="Selected channel is not an ACTIVE managed channel.")

        media_path = None
        media_name = None
        media_type = None
        if media_file and media_file.filename:
            media_path, media_name, media_type = await store_schedule_media(media_file, SCHEDULE_MEDIA_DIR)
        stored_message_text = message_text or MEDIA_ONLY_SENTINEL

        try:
            db_user_id = _resolve_db_user_id(app, user_id)
            record = await app.state.schedule_service.create_direct(
                channel_identifier=selected_channel.chat_identifier,
                channel_title=selected_channel.title or (channel_title.strip() or None),
                scheduled_for_raw=scheduled_for,
                message_text=stored_message_text,
                media_path=media_path,
                media_name=media_name,
                media_type=media_type,
                created_by_user_id=db_user_id,
            )
        except ValueError:
            return dashboard_redirect(error="Invalid schedule time. Use picker or YYYY-MM-DD HH:MM.")

        if record and record.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_SCHEDULE_CREATE",
                target_type="SCHEDULE",
                target_id=str(record.id),
                details=f"{record.channel_identifier}|{record.scheduled_for}",
            )
        notice = "Schedule created."
        if record and record.id:
            notice = f"Schedule #{record.id} created for {record.channel_identifier}."
        return dashboard_redirect(notice=notice)

    @app.post("/dashboard/entities/status")
    async def update_entity_status(
        request: Request,
        section: str = Form(...),
        entity_id: int = Form(...),
        target_status: str = Form(...),
        csrf_token: str = Form(...),
        next_url: str = Form(""),
        q: str = Form(""),
        status: str = Form("ALL"),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if target_status.upper() == "BLOCKED" and not has_sensitive_session(request):
            return RedirectResponse(url=reauth_redirect_url(q, status), status_code=302)

        updated = await app.state.entity_service.update_status(section, entity_id, target_status.upper())
        if updated and updated.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="ENTITY_STATUS_UPDATE",
                target_type=entity_target_type(section),
                target_id=str(updated.id),
                details=f"{updated.chat_identifier}|{updated.status}",
            )
        next_url = safe_next_url(next_url)
        if next_url:
            return RedirectResponse(url=next_url, status_code=302)
        return RedirectResponse(url=f"/dashboard?q={q}&status={status}", status_code=302)

    @app.get("/dashboard/entity/{section}/{entity_id}", response_class=HTMLResponse)
    async def entity_detail(request: Request, section: str, entity_id: int) -> HTMLResponse:
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        role_keys = _current_role_keys(app, user_id)
        if not role_keys:
            response = RedirectResponse(url="/", status_code=302)
            response.delete_cookie("em_session")
            return response

        normalized_section = "Channels" if section.lower().startswith("channel") else "Groups"
        record = await app.state.entity_service.get_entity(normalized_section, entity_id)
        if not record:
            return HTMLResponse("Entity not found.", status_code=404)

        activity_lines = await load_entity_detail_activity(app, normalized_section, entity_id, limit=12)
        csrf_token = read_csrf_token(request)
        sensitive_mode = has_sensitive_session(request)
        response = HTMLResponse(
            entity_detail_page(
                user_id=user_id,
                roles=sorted(role_keys),
                section=normalized_section,
                record=record,
                activity_lines=activity_lines,
                csrf_token=csrf_token,
                sensitive_mode=sensitive_mode,
            )
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.post("/dashboard/automation/create")
    async def create_automation(request: Request, template_key: str = Form(...), csrf_token: str = Form(...)):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        record = await app.state.automation_service.create_rule(template_key, _resolve_db_user_id(app, user_id))
        if record and record.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="AUTOMATION_RULE_UPSERT",
                target_type="AUTOMATION",
                target_id=str(record.id),
                details=f"{record.template_key}|{record.status}",
            )
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.post("/dashboard/automation/create-custom")
    async def create_custom_automation(
        request: Request,
        rule_name: str = Form(""),
        schedule_key: str = Form(...),
        message_text: str = Form(...),
        cooldown_minutes: int = Form(0),
        quiet_hours_start: int | None = Form(None),
        quiet_hours_end: int | None = Form(None),
        csrf_token: str = Form(...),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not message_text.strip():
            return RedirectResponse(url="/dashboard?error=Custom%20message%20is%20required.", status_code=302)
        timing_error = validate_automation_timing(cooldown_minutes, quiet_hours_start, quiet_hours_end)
        if timing_error:
            return RedirectResponse(url=f"/dashboard?error={quote(timing_error, safe='')}", status_code=302)

        record = await app.state.automation_service.create_custom_owner_alert(
            rule_name=rule_name,
            schedule_key=schedule_key,
            message_text=message_text,
            cooldown_minutes=cooldown_minutes,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            created_by_user_id=_resolve_db_user_id(app, user_id),
        )
        if record and record.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="AUTOMATION_CUSTOM_RULE_CREATE",
                target_type="AUTOMATION",
                target_id=str(record.id),
                details=f"{record.template_key}|{record.schedule_key}",
            )
        return RedirectResponse(url="/dashboard?notice=Custom%20automation%20created.", status_code=302)

    @app.post("/dashboard/automation/create-condition")
    async def create_condition_automation(
        request: Request,
        rule_name: str = Form(""),
        trigger_keys: list[str] = Form(...),
        schedule_key: str = Form(...),
        threshold: int = Form(1),
        message_text: str = Form(...),
        cooldown_minutes: int = Form(0),
        quiet_hours_start: int | None = Form(None),
        quiet_hours_end: int | None = Form(None),
        csrf_token: str = Form(...),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not message_text.strip():
            return RedirectResponse(url="/dashboard?error=Condition%20message%20is%20required.", status_code=302)
        timing_error = validate_automation_timing(cooldown_minutes, quiet_hours_start, quiet_hours_end)
        if timing_error:
            return RedirectResponse(url=f"/dashboard?error={quote(timing_error, safe='')}", status_code=302)

        record = await app.state.automation_service.create_custom_condition_alert(
            rule_name=rule_name,
            schedule_key=schedule_key,
            trigger_keys=trigger_keys,
            threshold=threshold,
            message_text=message_text,
            cooldown_minutes=cooldown_minutes,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            created_by_user_id=_resolve_db_user_id(app, user_id),
        )
        if record and record.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="AUTOMATION_CONDITION_RULE_CREATE",
                target_type="AUTOMATION",
                target_id=str(record.id),
                details=f"{record.template_key}|{record.schedule_key}",
        )
        return RedirectResponse(url="/dashboard?notice=Conditional%20automation%20created.", status_code=302)

    @app.post("/dashboard/automation/update-custom")
    async def update_custom_automation(
        request: Request,
        rule_id: int = Form(...),
        rule_kind: str = Form(...),
        rule_name: str = Form(""),
        schedule_key: str = Form(...),
        message_text: str = Form(...),
        threshold: int = Form(1),
        trigger_keys: list[str] = Form([]),
        cooldown_minutes: int = Form(0),
        quiet_hours_start: int | None = Form(None),
        quiet_hours_end: int | None = Form(None),
        csrf_token: str = Form(...),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not message_text.strip():
            return RedirectResponse(url="/dashboard?error=Custom%20message%20is%20required.", status_code=302)
        timing_error = validate_automation_timing(cooldown_minutes, quiet_hours_start, quiet_hours_end)
        if timing_error:
            return RedirectResponse(url=f"/dashboard?error={quote(timing_error, safe='')}", status_code=302)

        normalized_kind = rule_kind.strip().upper()
        if normalized_kind == "CUSTOM_CONDITION_ALERT" and not [item for item in trigger_keys if item.strip()]:
            return RedirectResponse(url="/dashboard?error=Select%20at%20least%20one%20trigger.", status_code=302)

        record = await app.state.automation_service.update_custom_rule(
            rule_id=rule_id,
            rule_name=rule_name,
            schedule_key=schedule_key,
            message_text=message_text,
            threshold=threshold if normalized_kind == "CUSTOM_CONDITION_ALERT" else None,
            trigger_keys=trigger_keys if normalized_kind == "CUSTOM_CONDITION_ALERT" else None,
            cooldown_minutes=cooldown_minutes,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
        )
        if not record:
            return RedirectResponse(url="/dashboard?error=Custom%20automation%20update%20failed.", status_code=302)

        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="AUTOMATION_CUSTOM_RULE_UPDATE",
            target_type="AUTOMATION",
            target_id=str(record.id),
            details=f"{record.template_key}|{record.schedule_key}",
        )
        return RedirectResponse(url="/dashboard?notice=Custom%20automation%20updated.", status_code=302)

    @app.post("/dashboard/automation/toggle")
    async def toggle_automation(request: Request, rule_id: int = Form(...), csrf_token: str = Form(...)):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        record = await app.state.automation_service.toggle_rule(rule_id)
        if record and record.id:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="AUTOMATION_RULE_TOGGLE",
                target_type="AUTOMATION",
                target_id=str(record.id),
                details=f"{record.template_key}|{record.status}",
            )
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.post("/dashboard/automation/duplicate")
    async def duplicate_automation(request: Request, rule_id: int = Form(...), csrf_token: str = Form(...)):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)

        record = await app.state.automation_service.duplicate_rule(rule_id, _resolve_db_user_id(app, user_id))
        if not record:
            return RedirectResponse(url="/dashboard?error=Automation%20duplicate%20failed.", status_code=302)
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="AUTOMATION_RULE_DUPLICATE",
            target_type="AUTOMATION",
            target_id=str(record.id),
            details=f"{record.template_key}|{record.schedule_key}",
        )
        return RedirectResponse(url="/dashboard?notice=Automation%20rule%20duplicated.", status_code=302)

    @app.post("/dashboard/automation/run-now")
    async def run_automation_now(request: Request, rule_id: int = Form(...), csrf_token: str = Form(...)):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not app.state.bot_api:
            return RedirectResponse(url="/dashboard?error=Bot%20API%20is%20not%20configured.", status_code=302)

        record = await app.state.automation_service.get_rule(rule_id)
        if not record:
            return RedirectResponse(url="/dashboard?error=Automation%20rule%20not%20found.", status_code=302)

        runner = AutomationRunner(app.state.context, app.state.bot_api, poll_interval_seconds=60)
        try:
            await runner.run_rule_once(record, mark_run=False)
        except Exception:
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="AUTOMATION_RULE_RUN_NOW_FAILED",
                target_type="AUTOMATION",
                target_id=str(rule_id),
                details=record.template_key,
            )
            return RedirectResponse(url="/dashboard?error=Automation%20run%20failed.", status_code=302)

        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="AUTOMATION_RULE_RUN_NOW",
            target_type="AUTOMATION",
            target_id=str(rule_id),
            details=record.template_key,
        )
        return RedirectResponse(url="/dashboard?notice=Automation%20rule%20ran%20now.", status_code=302)

    @app.post("/dashboard/automation/delete")
    async def delete_automation(request: Request, rule_id: int = Form(...), csrf_token: str = Form(...)):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if not has_sensitive_session(request):
            return RedirectResponse(url=reauth_redirect_url(), status_code=302)

        record = await app.state.automation_service.get_rule(rule_id)
        await app.state.automation_service.delete_rule(rule_id)
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key="AUTOMATION_RULE_DELETE",
            target_type="AUTOMATION",
            target_id=str(rule_id),
            details=record.template_key if record else None,
        )
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.post("/dashboard/schedules/status")
    async def update_schedule_status(
        request: Request,
        schedule_id: int = Form(...),
        target_status: str = Form(...),
        csrf_token: str = Form(...),
        q: str = Form(""),
        status: str = Form("ALL"),
    ):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return RedirectResponse(url="/", status_code=302)
        if not _current_role_keys(app, user_id):
            return RedirectResponse(url="/", status_code=302)
        if not validate_csrf(request, csrf_token):
            return HTMLResponse("Invalid CSRF token.", status_code=403)
        if target_status.upper() == "CANCELED" and not has_sensitive_session(request):
            return RedirectResponse(url=reauth_redirect_url(q, status), status_code=302)

        target_status = target_status.upper()
        if target_status not in {"CANCELED", "PENDING", "PAUSED", "SKIP_NEXT"}:
            return HTMLResponse("Invalid schedule status.", status_code=400)

        if target_status == "SKIP_NEXT":
            updated = await app.state.schedule_service.skip_next(schedule_id)
            if not updated:
                return dashboard_redirect(error="Could not skip the next recurring run.", query=q, status_filter=status)
            await record_audit_event(
                app,
                actor_user_id=user_id,
                action_key="WEB_SKIP_NEXT_RECURRING_SCHEDULE",
                target_type="SCHEDULE",
                target_id=str(schedule_id),
                details=f"next={updated.scheduled_for}",
            )
            return dashboard_redirect(notice="Skipped next recurring run.", query=q, status_filter=status)

        await app.state.schedule_service.update_status(schedule_id, target_status)
        action_map = {
            "CANCELED": "WEB_CANCEL_SCHEDULE",
            "PENDING": "WEB_RESUME_OR_RETRY_SCHEDULE",
            "PAUSED": "WEB_PAUSE_RECURRING_SCHEDULE",
        }
        await record_audit_event(
            app,
            actor_user_id=user_id,
            action_key=action_map.get(target_status, "WEB_UPDATE_SCHEDULE"),
            target_type="SCHEDULE",
            target_id=str(schedule_id),
            details=target_status,
        )
        return RedirectResponse(url=f"/dashboard?q={q}&status={status}", status_code=302)

    @app.get("/api/report")
    async def api_report(request: Request):
        user_id = _require_session_user_id(request)
        if user_id is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        role_keys = _current_role_keys(app, user_id)
        if not role_keys:
            return JSONResponse({"error": "forbidden"}, status_code=403)

        bundle = await app.state.report_service.build_reports()
        return {
            "telegram_user_id": user_id,
            "roles": sorted(role_keys),
            "daily": bundle.daily_text,
            "weekly": bundle.weekly_text,
            "export": bundle.export_text,
        }

    return app

def _require_session_user_id(request: Request) -> int | None:
    return read_session_user_id(request)


def _current_role_keys(app: FastAPI, telegram_user_id: int) -> set[str]:
    if telegram_user_id in app.state.settings.owner_ids:
        return {"OWNER"}
    if not app.state.context.oracle_client:
        return set()
    repository = AccessRepository(app.state.context.oracle_client)
    user = repository.get_user_by_telegram_id(telegram_user_id)
    if not user:
        return set()
    return repository.get_role_keys_for_user(user.id)


def _resolve_db_user_id(app: FastAPI, telegram_user_id: int) -> int | None:
    if not app.state.context.oracle_client:
        return None
    repository = AccessRepository(app.state.context.oracle_client)
    if not app.state.context.core_roles_ready:
        repository.ensure_core_roles()
        app.state.context.core_roles_ready = True
    user = repository.get_user_by_telegram_id(telegram_user_id)
    if not user:
        user = repository.upsert_user(
            telegram_user_id=telegram_user_id,
            username=None,
            display_name=f"Web Admin {telegram_user_id}",
        )
        if telegram_user_id in app.state.settings.owner_ids and user.id is not None:
            repository.assign_role_by_key(user.id, "OWNER")
    return user.id if user else None


app = build_app()
