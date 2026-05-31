from __future__ import annotations


def validate_automation_timing(
    cooldown_minutes: int,
    quiet_hours_start: int | None,
    quiet_hours_end: int | None,
) -> str | None:
    if cooldown_minutes < 0 or cooldown_minutes > 10080:
        return "Cooldown must be between 0 and 10080 minutes."
    if (quiet_hours_start is None) ^ (quiet_hours_end is None):
        return "Set both quiet start and quiet end hours, or leave both blank."
    if quiet_hours_start is None and quiet_hours_end is None:
        return None
    if quiet_hours_start is None or quiet_hours_end is None:
        return "Set both quiet start and quiet end hours."
    if not (0 <= quiet_hours_start <= 23 and 0 <= quiet_hours_end <= 23):
        return "Quiet hours must use 0 to 23."
    if quiet_hours_start == quiet_hours_end:
        return "Quiet start and quiet end cannot be the same hour."
    return None
