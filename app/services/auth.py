from app.models.access import AccessProfile


FULL_ACCESS_ROLES = {"OWNER", "SUPER_ADMIN"}
GROUP_ACCESS_ROLES = FULL_ACCESS_ROLES | {"GROUP_MANAGER", "MODERATOR"}
CHANNEL_ACCESS_ROLES = FULL_ACCESS_ROLES | {"CHANNEL_MANAGER"}
REPORT_ACCESS_ROLES = FULL_ACCESS_ROLES | {"CHANNEL_MANAGER", "GROUP_MANAGER", "MODERATOR", "VIEWER"}
ALL_ADMIN_ROLES = FULL_ACCESS_ROLES | {"CHANNEL_MANAGER", "GROUP_MANAGER", "MODERATOR", "VIEWER"}
QUICK_ACCESS_ROLES = FULL_ACCESS_ROLES | {"CHANNEL_MANAGER", "GROUP_MANAGER", "MODERATOR"}


SECTION_ROLE_MAP: dict[str, set[str]] = {
    "Home": ALL_ADMIN_ROLES,
    "Create": QUICK_ACCESS_ROLES,
    "Review": QUICK_ACCESS_ROLES,
    "Status": ALL_ADMIN_ROLES,
    "More": ALL_ADMIN_ROLES,
    "Channels": CHANNEL_ACCESS_ROLES,
    "Groups": GROUP_ACCESS_ROLES,
    "Broadcast": CHANNEL_ACCESS_ROLES,
    "Bots": FULL_ACCESS_ROLES,
    "Automation": FULL_ACCESS_ROLES,
    "Reports": REPORT_ACCESS_ROLES,
    "Settings": FULL_ACCESS_ROLES,
}


ACTION_ROLE_MAP: dict[tuple[str, str], set[str]] = {
    ("Home", "New Post"): CHANNEL_ACCESS_ROLES,
    ("Home", "New Schedule"): CHANNEL_ACCESS_ROLES,
    ("Home", "Review Waiting"): QUICK_ACCESS_ROLES,
    ("Home", "Alerts"): REPORT_ACCESS_ROLES,
    ("Home", "Mode"): ALL_ADMIN_ROLES,
    ("Home", "More"): ALL_ADMIN_ROLES,
    ("Create", "Post"): CHANNEL_ACCESS_ROLES,
    ("Create", "Schedule"): CHANNEL_ACCESS_ROLES,
    ("Create", "Broadcast"): CHANNEL_ACCESS_ROLES,
    ("Create", "Add Channel"): CHANNEL_ACCESS_ROLES,
    ("Create", "Add Group"): GROUP_ACCESS_ROLES,
    ("Review", "Pending Channels"): CHANNEL_ACCESS_ROLES,
    ("Review", "Pending Groups"): GROUP_ACCESS_ROLES,
    ("Review", "Schedules"): CHANNEL_ACCESS_ROLES,
    ("Review", "Alerts"): REPORT_ACCESS_ROLES,
    ("Status", "Channels"): CHANNEL_ACCESS_ROLES,
    ("Status", "Groups"): GROUP_ACCESS_ROLES,
    ("Status", "Bots"): FULL_ACCESS_ROLES,
    ("Status", "Reports"): REPORT_ACCESS_ROLES,
    ("More", "Channels"): CHANNEL_ACCESS_ROLES,
    ("More", "Groups"): GROUP_ACCESS_ROLES,
    ("More", "Bots"): FULL_ACCESS_ROLES,
    ("More", "Automation"): FULL_ACCESS_ROLES,
    ("More", "Settings"): FULL_ACCESS_ROLES,
    ("More", "Mode"): ALL_ADMIN_ROLES,
    ("Channels", "Add"): CHANNEL_ACCESS_ROLES,
    ("Channels", "Pending"): CHANNEL_ACCESS_ROLES,
    ("Channels", "List"): CHANNEL_ACCESS_ROLES,
    ("Channels", "Post"): CHANNEL_ACCESS_ROLES,
    ("Channels", "Schedule"): CHANNEL_ACCESS_ROLES,
    ("Channels", "Analytics"): FULL_ACCESS_ROLES,
    ("Groups", "Add"): GROUP_ACCESS_ROLES,
    ("Groups", "Pending"): GROUP_ACCESS_ROLES,
    ("Groups", "List"): GROUP_ACCESS_ROLES,
    ("Groups", "Moderation"): GROUP_ACCESS_ROLES,
    ("Groups", "Warnings"): GROUP_ACCESS_ROLES,
    ("Groups", "Filters"): GROUP_ACCESS_ROLES,
    ("Groups", "Welcome"): GROUP_ACCESS_ROLES,
    ("Broadcast", "Send All"): CHANNEL_ACCESS_ROLES,
    ("Broadcast", "Select"): CHANNEL_ACCESS_ROLES,
    ("Broadcast", "Targets"): CHANNEL_ACCESS_ROLES,
    ("Bots", "Status"): FULL_ACCESS_ROLES,
    ("Bots", "Logs"): FULL_ACCESS_ROLES,
    ("Bots", "Configs"): FULL_ACCESS_ROLES,
    ("Bots", "Actions"): FULL_ACCESS_ROLES,
    ("Automation", "Facebook Promo AI"): FULL_ACCESS_ROLES,
    ("Automation", "Create"): FULL_ACCESS_ROLES,
    ("Automation", "Rules"): FULL_ACCESS_ROLES,
    ("Automation", "Templates"): FULL_ACCESS_ROLES,
    ("Reports", "Daily"): REPORT_ACCESS_ROLES,
    ("Reports", "Weekly"): REPORT_ACCESS_ROLES,
    ("Reports", "Export"): REPORT_ACCESS_ROLES,
}


def is_owner(profile: AccessProfile) -> bool:
    return profile.is_owner


def can_access_admin_ui(profile: AccessProfile) -> bool:
    return profile.is_admin


def can_open_section(profile: AccessProfile, section: str) -> bool:
    allowed_roles = SECTION_ROLE_MAP.get(section, FULL_ACCESS_ROLES)
    return bool(profile.role_keys & allowed_roles)


def can_run_section_action(profile: AccessProfile, section: str, action: str) -> bool:
    allowed_roles = ACTION_ROLE_MAP.get((section, action), SECTION_ROLE_MAP.get(section, FULL_ACCESS_ROLES))
    return bool(profile.role_keys & allowed_roles)


def get_allowed_sections(profile: AccessProfile, sections: list[str] | tuple[str, ...]) -> list[str]:
    return [section for section in sections if can_open_section(profile, section)]


def get_visible_main_menu_keys(profile: AccessProfile, menu_keys: list[str] | tuple[str, ...]) -> list[str]:
    return [section for section in menu_keys if can_open_section(profile, section)]
