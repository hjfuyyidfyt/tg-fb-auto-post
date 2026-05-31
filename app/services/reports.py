from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.runtime import AppContext
from app.repositories.audit import AuditRepository
from app.services.entities import ManagedEntityService
from app.services.filters import GroupFilterService
from app.services.group_events import GroupEventService
from app.services.schedule import ScheduleService
from app.services.warnings import WarningService


@dataclass(slots=True)
class ReportBundle:
    daily_text: str
    weekly_text: str
    export_text: str


class ReportService:
    def __init__(self, app_context: AppContext, redis_client: object | None = None) -> None:
        self.app_context = app_context
        self.redis_client = redis_client
        self.entity_service = ManagedEntityService(app_context, redis_client=redis_client)
        self.schedule_service = ScheduleService(app_context, redis_client=redis_client)
        self.warning_service = WarningService(redis_client=redis_client)
        self.filter_service = GroupFilterService(redis_client=redis_client)
        self.group_event_service = GroupEventService(redis_client=redis_client)

    async def build_reports(self) -> ReportBundle:
        active_channels = await self.entity_service.list_channels()
        active_groups = await self.entity_service.list_groups()
        pending_channels = await self.entity_service.list_channels_by_status("PENDING")
        pending_groups = await self.entity_service.list_groups_by_status("PENDING")
        pending_schedules = await self.schedule_service.list_pending()
        recent_activity = await self._list_recent_activity()

        warning_lines: list[str] = []
        protection_lines: list[str] = []

        for record in active_groups[:10]:
            group_key = record.chat_identifier.replace("@", "u_")
            warnings = await self.warning_service.get_top_warnings(group_key, limit=3)
            if warnings:
                top = ", ".join(f"{item.label}:{item.count}" for item in warnings[:3])
                warning_lines.append(f"- {record.title or record.chat_identifier} -> {top}")

            filter_state = await self.filter_service.get_state(group_key)
            event_state = await self.group_event_service.get_state(group_key)
            toggles: list[str] = []
            if filter_state.anti_link_enabled:
                toggles.append("anti-link")
            if filter_state.bad_word_enabled:
                toggles.append("bad-words")
            if event_state.welcome_enabled:
                toggles.append("welcome")
            if event_state.join_log_enabled:
                toggles.append("join-logs")
            if toggles:
                protection_lines.append(f"- {record.title or record.chat_identifier} -> {', '.join(toggles)}")

        daily_lines = [
            "Daily dashboard",
            "",
            f"ACTIVE channels: {len(active_channels)}",
            f"PENDING channels: {len(pending_channels)}",
            f"ACTIVE groups: {len(active_groups)}",
            f"PENDING groups: {len(pending_groups)}",
            f"Pending schedules: {len(pending_schedules)}",
            "",
            "Hot warning groups:",
            *(warning_lines or ["- None"]),
        ]

        weekly_lines = [
            "Weekly operations report",
            "",
            f"ACTIVE channels: {len(active_channels)}",
            f"ACTIVE groups: {len(active_groups)}",
            f"Pending review items: {len(pending_channels) + len(pending_groups)}",
            f"Pending schedules: {len(pending_schedules)}",
            "",
            "Protection coverage:",
            *(protection_lines or ["- No toggles enabled yet"]),
            "",
            "Recent activity:",
            *(recent_activity or ["- No recent audit events found"]),
        ]

        export_lines = [
            "EXPORT REPORT",
            f"channels_active={len(active_channels)}",
            f"channels_pending={len(pending_channels)}",
            f"groups_active={len(active_groups)}",
            f"groups_pending={len(pending_groups)}",
            f"schedules_pending={len(pending_schedules)}",
            "",
            "[warning_hotspots]",
            *(warning_lines or ["- none"]),
            "",
            "[protection_coverage]",
            *(protection_lines or ["- none"]),
            "",
            "[recent_activity]",
            *(recent_activity or ["- none"]),
        ]

        return ReportBundle(
            daily_text="\n".join(daily_lines),
            weekly_text="\n".join(weekly_lines),
            export_text="\n".join(export_lines),
        )

    async def _list_recent_activity(self) -> list[str]:
        if not self.app_context.oracle_client:
            return []

        rows = await asyncio.to_thread(AuditRepository(self.app_context.oracle_client).list_recent, 8)
        lines: list[str] = []
        for row in rows:
            actor_user_id, action_key, target_type, target_id, details, created_at = row
            time_label = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "unknown"
            target_label = f"{target_type}:{target_id}" if target_type and target_id else (target_type or "-")
            detail_label = f" | {details}" if details else ""
            lines.append(f"- {time_label} | {action_key} | actor={actor_user_id or '-'} | {target_label}{detail_label}")
        return lines
