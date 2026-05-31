from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _build_quick_target_rows(
    channels: list[tuple[int, str, str | None, bool, bool]],
    action_prefix: str,
) -> list[list[InlineKeyboardButton]]:
    quick_rows: list[list[InlineKeyboardButton]] = []
    if not channels:
        return quick_rows

    labels: list[InlineKeyboardButton] = []
    for entity_id, identifier, title, is_favorite, is_recent in channels[:3]:
        label = title or identifier
        if is_recent:
            text = f"🕘 {label[:14]}"
        elif is_favorite:
            text = f"⭐ {label[:14]}"
        else:
            text = label[:14]
        labels.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{action_prefix}:{entity_id}",
            )
        )
    if labels:
        quick_rows.append(labels)
    return quick_rows


SECTION_ACTIONS: dict[str, list[str]] = {
    "Home": ["New Post", "New Schedule", "Review", "Alerts", "Mode", "More"],
    "Create": ["Post", "Schedule", "Broadcast", "Add Channel", "Add Group"],
    "Review": ["Pending Channels", "Pending Groups", "Schedules", "Alerts"],
    "Status": ["Channels", "Groups", "Bots", "Reports"],
    "More": ["Channels", "Groups", "Bots", "Automation", "Settings", "Mode"],
    "Channels": ["Add", "Pending", "View", "Post", "Schedule", "Analytics"],
    "Groups": ["Add", "Pending", "View", "Moderation", "Warnings", "Filters", "Welcome"],
    "Broadcast": ["Send All", "Select", "Targets"],
    "Bots": ["Status", "Logs", "Settings", "Actions"],
    "Automation": ["Facebook Promo AI"],
    "Reports": ["Daily", "Weekly", "Export"],
    "Settings": ["Roles", "Language", "Alerts"],
}

ACTION_LABELS: dict[tuple[str, str], str] = {
    ("Home", "New Post"): "📝 New Post",
    ("Home", "New Schedule"): "⏰ New Schedule",
    ("Home", "Review"): "✅ Review",
    ("Home", "Alerts"): "🚨 Alerts",
    ("Home", "Mode"): "🧭 Mode",
    ("Home", "More"): "⚙️ More",
    ("Create", "Post"): "📝 Post",
    ("Create", "Schedule"): "⏰ Schedule",
    ("Create", "Broadcast"): "📤 Broadcast",
    ("Create", "Add Channel"): "➕ Add Channel",
    ("Create", "Add Group"): "➕ Add Group",
    ("Review", "Pending Channels"): "📢 Pending Channels",
    ("Review", "Pending Groups"): "👥 Pending Groups",
    ("Review", "Schedules"): "⏰ Schedules",
    ("Review", "Alerts"): "🚨 Alerts",
    ("Status", "Channels"): "📢 Channels",
    ("Status", "Groups"): "👥 Groups",
    ("Status", "Bots"): "🤖 Bots",
    ("Status", "Reports"): "📊 Reports",
    ("More", "Channels"): "📢 Channels",
    ("More", "Groups"): "👥 Groups",
    ("More", "Bots"): "🤖 Bots",
    ("More", "Automation"): "⚙️ Automation",
    ("More", "Settings"): "🛠️ Settings",
    ("More", "Mode"): "🧭 Mode",
    ("Channels", "Add"): "➕ Add",
    ("Channels", "Pending"): "⏳ Pending",
    ("Channels", "View"): "📋 View",
    ("Channels", "Post"): "📝 Post",
    ("Channels", "Schedule"): "⏰ Schedule",
    ("Channels", "Analytics"): "📈 Analytics",
    ("Groups", "Add"): "➕ Add",
    ("Groups", "Pending"): "⏳ Pending",
    ("Groups", "View"): "📋 View",
    ("Groups", "Moderation"): "🛡️ Moderation",
    ("Groups", "Warnings"): "⚠️ Warnings",
    ("Groups", "Filters"): "🧹 Filters",
    ("Groups", "Welcome"): "👋 Welcome",
    ("Broadcast", "Send All"): "📤 Send All",
    ("Broadcast", "Select"): "🎯 Select",
    ("Broadcast", "Targets"): "📋 Targets",
    ("Bots", "Status"): "🟢 Status",
    ("Bots", "Logs"): "🧾 Logs",
    ("Bots", "Settings"): "⚙️ Settings",
    ("Bots", "Actions"): "▶️ Actions",
    ("Automation", "Create"): "➕ Create",
    ("Automation", "Rules"): "📋 Rules",
    ("Automation", "Templates"): "🧩 Templates",
    ("Reports", "Daily"): "📅 Daily",
    ("Reports", "Weekly"): "📈 Weekly",
    ("Reports", "Export"): "📦 Export",
    ("Settings", "Roles"): "👤 Roles",
    ("Settings", "Language"): "🌐 Language",
    ("Settings", "Alerts"): "🔔 Alerts",
}


ACTION_LABELS[("Automation", "Facebook Promo AI")] = "🧠 Facebook Promo AI"


def build_section_actions(section: str) -> list[str]:
    return SECTION_ACTIONS.get(section, [])


def build_section_actions_keyboard(section: str) -> InlineKeyboardMarkup:
    actions = build_section_actions(section)
    rows: list[list[InlineKeyboardButton]] = []

    for index in range(0, len(actions), 2):
        chunk = actions[index : index + 2]
        rows.append(
            [
                InlineKeyboardButton(
                    text=ACTION_LABELS.get((section, action), action),
                    callback_data=f"section:{section}:{action}",
                )
                for action in chunk
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(text="Home", callback_data="nav:home"),
            InlineKeyboardButton(text="Back", callback_data="nav:back"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_review_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Pending Channels",
                    callback_data="section:Channels:Pending",
                ),
                InlineKeyboardButton(
                    text="👥 Pending Groups",
                    callback_data="section:Groups:Pending",
                ),
            ],
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"),
            ],
        ]
    )


def build_onboarding_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Channel", callback_data="section:Create:Add Channel"),
                InlineKeyboardButton(text="📝 New Post", callback_data="section:Home:New Post"),
            ],
            [
                InlineKeyboardButton(text="✅ Review Pending", callback_data="section:Home:Review"),
                InlineKeyboardButton(text="⚡ Create", callback_data="nav:home"),
            ],
        ]
    )


def build_success_next_keyboard(kind: str) -> InlineKeyboardMarkup:
    presets: dict[str, list[list[tuple[str, str]]]] = {
        "post_sent": [
            [("📝 New Post", "section:Home:New Post"), ("⏰ Schedule", "section:Create:Schedule")],
            [("🏠 Home", "nav:home")],
        ],
        "broadcast_sent": [
            [("📤 Broadcast Again", "section:Create:Broadcast"), ("📊 Status", "section:Home:Status")],
            [("🏠 Home", "nav:home")],
        ],
        "schedule_saved": [
            [("📋 View Schedules", "section:Review:Schedules"), ("⏰ New Schedule", "section:Create:Schedule")],
            [("🏠 Home", "nav:home")],
        ],
        "channel_saved": [
            [("📝 Post Now", "section:Home:New Post"), ("⏰ Schedule", "section:Create:Schedule")],
            [("📊 Channels", "section:Status:Channels"), ("🏠 Home", "nav:home")],
        ],
        "group_saved": [
            [("🛡️ Moderation", "section:Groups:Moderation"), ("📊 Groups", "section:Status:Groups")],
            [("🏠 Home", "nav:home")],
        ],
        "bot_saved": [
            [("🟢 Bot Status", "section:Bots:Status"), ("▶️ Add Another", "section:Bots:Actions")],
            [("🏠 Home", "nav:home")],
        ],
        "review_done": [
            [("✅ Review More", "section:Home:Review"), ("📋 View Channels", "section:Status:Channels")],
            [("🏠 Home", "nav:home")],
        ],
        "review_done_groups": [
            [("✅ Review More", "section:Home:Review"), ("📋 View Groups", "section:Status:Groups")],
            [("🏠 Home", "nav:home")],
        ],
    }

    rows = [
        [InlineKeyboardButton(text=text, callback_data=callback_data) for text, callback_data in row]
        for row in presets.get(kind, [[("🏠 Home", "nav:home")]])
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_search_recovery_keyboard(context: str) -> InlineKeyboardMarkup:
    extra_button = {
        "post": ("📝 New Post", "section:Home:New Post"),
        "schedule": ("⏰ New Schedule", "section:Create:Schedule"),
        "broadcast": ("📤 Broadcast", "section:Create:Broadcast"),
    }.get(context, ("🏠 Home", "nav:home"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Favorites", callback_data=f"picker:{context}:favorites"),
                InlineKeyboardButton(text="📋 All", callback_data=f"picker:{context}:all"),
            ],
            [
                InlineKeyboardButton(text="🔎 Search Again", callback_data=f"pickersearch:{context}"),
                InlineKeyboardButton(text=extra_button[0], callback_data=extra_button[1]),
            ],
        ]
    )


def build_empty_recovery_keyboard(context: str) -> InlineKeyboardMarkup:
    if context == "post":
        rows = [
            [
                InlineKeyboardButton(text="➕ Add Channel", callback_data="section:Create:Add Channel"),
                InlineKeyboardButton(text="✅ Review", callback_data="section:Home:Review"),
            ],
            [InlineKeyboardButton(text="🏠 Home", callback_data="nav:home")],
        ]
    elif context == "schedule":
        rows = [
            [
                InlineKeyboardButton(text="➕ Add Channel", callback_data="section:Create:Add Channel"),
                InlineKeyboardButton(text="✅ Review", callback_data="section:Home:Review"),
            ],
            [
                InlineKeyboardButton(text="📋 Channels", callback_data="section:Status:Channels"),
                InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"),
            ],
        ]
    elif context == "broadcast":
        rows = [
            [
                InlineKeyboardButton(text="➕ Add Channel", callback_data="section:Create:Add Channel"),
                InlineKeyboardButton(text="✅ Review", callback_data="section:Home:Review"),
            ],
            [InlineKeyboardButton(text="🏠 Home", callback_data="nav:home")],
        ]
    elif context == "groups":
        rows = [
            [
                InlineKeyboardButton(text="➕ Add Group", callback_data="section:Create:Add Group"),
                InlineKeyboardButton(text="✅ Review", callback_data="section:Home:Review"),
            ],
            [
                InlineKeyboardButton(text="📋 Groups", callback_data="section:Status:Groups"),
                InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"),
            ],
        ]
    else:
        rows = [[InlineKeyboardButton(text="🏠 Home", callback_data="nav:home")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_ai_keyboard(
    has_access: bool,
    is_active: bool,
    has_notes: bool,
    has_plan: bool = False,
) -> InlineKeyboardMarkup:
    status_label = "⏸ Pause" if is_active else "▶️ Activate"
    notes_label = "🧠 Update AI Brief" if has_notes else "🧠 Tell AI"
    access_label = "🔑 Update Access" if has_access else "🔑 Facebook Access"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 New Promo Task", callback_data="fbpromo:newtask"),
            ],
            [
                InlineKeyboardButton(text=access_label, callback_data="fbpromo:access"),
                InlineKeyboardButton(text=notes_label, callback_data="fbpromo:brief"),
            ],
            [
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text=status_label, callback_data="fbpromo:toggle"),
            ],
            [
                InlineKeyboardButton(text="🧪 Sample Flow", callback_data="fbpromo:sample"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:More:Automation"),
            ],
        ]
    )

def build_facebook_promo_ai_ready_keyboard(
    has_access: bool,
    is_active: bool,
    has_notes: bool,
    has_plan: bool = False,
    has_campaigns: bool = False,
) -> InlineKeyboardMarkup:
    status_label = "⏸ Pause" if is_active else "▶️ Activate"
    notes_label = "🧠 Update AI Brief" if has_notes else "🧠 Tell AI"
    access_label = "🔑 Update Access" if has_access else "🔑 Facebook Access"
    rows = [
        [InlineKeyboardButton(text="🚀 New Promo Task", callback_data="fbpromo:newtask")],
        [
            InlineKeyboardButton(text=access_label, callback_data="fbpromo:access"),
            InlineKeyboardButton(text=notes_label, callback_data="fbpromo:brief"),
        ],
        [
            InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
            InlineKeyboardButton(text=status_label, callback_data="fbpromo:toggle"),
        ],
    ]
    if has_plan:
        rows.append([InlineKeyboardButton(text="✍️ Generate Draft", callback_data="fbpromo:draft:generate")])
    rows.append(
        [
            InlineKeyboardButton(text="🧪 Sample Flow", callback_data="fbpromo:sample"),
            InlineKeyboardButton(text="◀️ Back", callback_data="section:More:Automation"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_facebook_promo_ai_hub_v2_keyboard(
    has_access: bool,
    is_active: bool,
    has_notes: bool,
    has_plan: bool = False,
    has_campaigns: bool = False,
) -> InlineKeyboardMarkup:
    status_label = "⏸ Pause" if is_active else "▶️ Activate"
    notes_label = "🧠 Update AI Brief" if has_notes else "🧠 Tell AI"
    access_label = "🔑 Update Access" if has_access else "🔑 Facebook Access"
    rows = [
        [InlineKeyboardButton(text="🚀 New Promo Task", callback_data="fbpromo:newtask")],
        [
            InlineKeyboardButton(text=access_label, callback_data="fbpromo:access"),
            InlineKeyboardButton(text=notes_label, callback_data="fbpromo:brief"),
        ],
        [
            InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
            InlineKeyboardButton(text=status_label, callback_data="fbpromo:toggle"),
        ],
    ]
    if has_plan:
        rows.append([InlineKeyboardButton(text="✍️ Generate Draft", callback_data="fbpromo:draft:generate")])
    if has_campaigns:
        rows.append([InlineKeyboardButton(text="📚 Saved Campaigns", callback_data="fbpromo:campaigns")])
    rows.append(
        [
            InlineKeyboardButton(text="🧪 Sample Flow", callback_data="fbpromo:sample"),
            InlineKeyboardButton(text="◀️ Back", callback_data="section:More:Automation"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_ai_hub_v3_keyboard(
    has_access: bool,
    is_active: bool,
    has_notes: bool,
    has_plan: bool = False,
    has_campaigns: bool = False,
    has_ready_queue: bool = False,
) -> InlineKeyboardMarkup:
    status_label = "⏸ Pause" if is_active else "▶️ Activate"
    notes_label = "🧠 Update AI Brief" if has_notes else "🧠 Tell AI"
    access_label = "🔑 Update Access" if has_access else "🔑 Facebook Access"
    rows = [
        [InlineKeyboardButton(text="💬 Start Promo Chat (Auto)", callback_data="fbpromo:startchat")],
        [InlineKeyboardButton(text="🚀 New Promo Task (Manual)", callback_data="fbpromo:newtask")],
        [
            InlineKeyboardButton(text=access_label, callback_data="fbpromo:access"),
            InlineKeyboardButton(text=notes_label, callback_data="fbpromo:brief"),
        ],
        [
            InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
            InlineKeyboardButton(text=status_label, callback_data="fbpromo:toggle"),
        ],
    ]
    if has_plan:
        rows.append([InlineKeyboardButton(text="✍️ Generate Draft", callback_data="fbpromo:draft:generate")])
    if has_campaigns:
        rows.append([InlineKeyboardButton(text="📚 Saved Campaigns", callback_data="fbpromo:campaigns")])
    if has_ready_queue:
        rows.append([InlineKeyboardButton(text="🚀 Ready Queue", callback_data="fbpromo:readyqueue")])
    rows.append(
        [
            InlineKeyboardButton(text="🧪 Sample Flow", callback_data="fbpromo:sample"),
            InlineKeyboardButton(text="◀️ Back", callback_data="section:More:Automation"),
        ]
    )
    rows.insert(-1, [InlineKeyboardButton(text="How To Use + Safety Guide", callback_data="fbpromo:guide")])
    rows.insert(-1, [InlineKeyboardButton(text="Image Safety Status", callback_data="fbpromo:image:status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_simple_keyboard(has_access: bool) -> InlineKeyboardMarkup:
    access_label = "🔑 Update Access" if has_access else "🔑 Facebook Access"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Chat with AI", callback_data="fbpromo:startchat")],
            [InlineKeyboardButton(text=access_label, callback_data="fbpromo:access")],
            [InlineKeyboardButton(text="◀️ Back", callback_data="section:More:Automation")],
        ]
    )


def build_facebook_promo_access_keyboard(has_page_id: bool, has_token: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆔 Page ID ✅" if has_page_id else "🆔 Page ID",
                    callback_data="fbpromo:set:page_id",
                ),
                InlineKeyboardButton(
                    text="🔐 Access Token ✅" if has_token else "🔐 Access Token",
                    callback_data="fbpromo:set:token",
                ),
            ],
            [
                InlineKeyboardButton(text="🧹 Clear Access", callback_data="fbpromo:clearaccess"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_access_v2_keyboard(has_page_id: bool, has_token: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Page ID saved" if has_page_id else "Page ID", callback_data="fbpromo:set:page_id"),
                InlineKeyboardButton(text="Token saved" if has_token else "Access Token", callback_data="fbpromo:set:token"),
            ],
            [
                InlineKeyboardButton(text="Dry Run Validate", callback_data="fbpromo:accessdry"),
                InlineKeyboardButton(text="Validate Access", callback_data="fbpromo:accessvalidate"),
            ],
            [InlineKeyboardButton(text="Access Setup Help", callback_data="fbpromo:accesshelp")],
            [
                InlineKeyboardButton(text="Clear Access", callback_data="fbpromo:clearaccess"),
                InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_brief_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Brand / Niche", callback_data="fbpromo:set:brand"),
                InlineKeyboardButton(text="💬 Tell AI", callback_data="fbpromo:set:brief"),
            ],
            [
                InlineKeyboardButton(text="🎛 Style Memory", callback_data="fbpromo:preferences"),
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_preferences_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👑 Premium", callback_data="fbpromo:pref:tone:premium"),
                InlineKeyboardButton(text="🤝 Friendly", callback_data="fbpromo:pref:tone:friendly"),
            ],
            [
                InlineKeyboardButton(text="📣 Bold", callback_data="fbpromo:pref:tone:bold"),
                InlineKeyboardButton(text="⚖️ Balanced", callback_data="fbpromo:pref:tone:balanced"),
            ],
            [
                InlineKeyboardButton(text="🙂 Light Emoji", callback_data="fbpromo:pref:emoji:light"),
                InlineKeyboardButton(text="🚫 No Emoji", callback_data="fbpromo:pref:emoji:none"),
            ],
            [
                InlineKeyboardButton(text="🎉 Playful Emoji", callback_data="fbpromo:pref:emoji:playful"),
            ],
            [
                InlineKeyboardButton(text="📨 Direct CTA", callback_data="fbpromo:pref:cta:direct"),
                InlineKeyboardButton(text="💬 Soft CTA", callback_data="fbpromo:pref:cta:soft"),
            ],
            [
                InlineKeyboardButton(text="📥 Inbox CTA", callback_data="fbpromo:pref:cta:inbox"),
                InlineKeyboardButton(text="🗨️ Comment CTA", callback_data="fbpromo:pref:cta:comment"),
            ],
            [
                InlineKeyboardButton(text="🏆 Premium Visual", callback_data="fbpromo:pref:image:premium"),
                InlineKeyboardButton(text="🖼 Minimal", callback_data="fbpromo:pref:image:minimal"),
            ],
            [
                InlineKeyboardButton(text="🌇 Lifestyle", callback_data="fbpromo:pref:image:lifestyle"),
                InlineKeyboardButton(text="🏷️ Sale Visual", callback_data="fbpromo:pref:image:sale"),
            ],
            [
                InlineKeyboardButton(text="🧭 Brand-fit", callback_data="fbpromo:pref:image:brand-fit"),
            ],
            [
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📣 Promotion", callback_data="fbpromo:goal:PROMO"),
                InlineKeyboardButton(text="💬 Engagement", callback_data="fbpromo:goal:ENGAGEMENT"),
            ],
            [
                InlineKeyboardButton(text="🛍 Product Sale", callback_data="fbpromo:goal:SALE"),
                InlineKeyboardButton(text="🎉 Offer Campaign", callback_data="fbpromo:goal:OFFER"),
            ],
            [
                InlineKeyboardButton(text="✨ Brand Awareness", callback_data="fbpromo:goal:BRAND"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_image_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🖼 Image needed", callback_data="fbpromo:image:NEEDED"),
                InlineKeyboardButton(text="✍️ Text only", callback_data="fbpromo:image:TEXT_ONLY"),
            ],
            [
                InlineKeyboardButton(text="🤖 Let AI decide", callback_data="fbpromo:image:AUTO"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_recommendation_keyboard(recommendations: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, title in recommendations[:3]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=title[:32],
                    callback_data=f"fbpromo:angle:{key}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Save This Plan", callback_data="fbpromo:plan:save"),
                InlineKeyboardButton(text="💬 Refine Plan", callback_data="fbpromo:plan:refine"),
            ],
            [
                InlineKeyboardButton(text="🔁 Pick Another Angle", callback_data="fbpromo:plan:angles"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_draft_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✨ Premium", callback_data="fbpromo:draft:preset:premium"),
                InlineKeyboardButton(text="✂️ Shorter", callback_data="fbpromo:draft:preset:shorter"),
            ],
            [
                InlineKeyboardButton(text="⚡ Urgent", callback_data="fbpromo:draft:preset:urgent"),
            ],
            [
                InlineKeyboardButton(text="💬 Refine Draft", callback_data="fbpromo:draft:refine"),
                InlineKeyboardButton(text="🔁 Regenerate", callback_data="fbpromo:draft:regenerate"),
            ],
            [
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_draft_v2_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✨ Premium", callback_data="fbpromo:draft:preset:premium"),
                InlineKeyboardButton(text="✂️ Shorter", callback_data="fbpromo:draft:preset:shorter"),
            ],
            [
                InlineKeyboardButton(text="⚡ Urgent", callback_data="fbpromo:draft:preset:urgent"),
            ],
            [
                InlineKeyboardButton(text="🖼 Minimal", callback_data="fbpromo:image:preset:minimal"),
                InlineKeyboardButton(text="🌇 Lifestyle", callback_data="fbpromo:image:preset:lifestyle"),
            ],
            [
                InlineKeyboardButton(text="🏷️ Sale Visual", callback_data="fbpromo:image:preset:sale"),
            ],
            [
                InlineKeyboardButton(text="🧩 Compare Variants", callback_data="fbpromo:draft:variants"),
            ],
            [
                InlineKeyboardButton(text="💬 Refine Draft", callback_data="fbpromo:draft:refine"),
                InlineKeyboardButton(text="🔁 Regenerate", callback_data="fbpromo:draft:regenerate"),
            ],
            [
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_draft_v3_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✨ Premium", callback_data="fbpromo:draft:preset:premium"),
                InlineKeyboardButton(text="✂️ Shorter", callback_data="fbpromo:draft:preset:shorter"),
            ],
            [
                InlineKeyboardButton(text="⚡ Urgent", callback_data="fbpromo:draft:preset:urgent"),
            ],
            [
                InlineKeyboardButton(text="🖼 Minimal", callback_data="fbpromo:image:preset:minimal"),
                InlineKeyboardButton(text="🌇 Lifestyle", callback_data="fbpromo:image:preset:lifestyle"),
            ],
            [
                InlineKeyboardButton(text="🏷️ Sale Visual", callback_data="fbpromo:image:preset:sale"),
            ],
            [
                InlineKeyboardButton(text="🧩 Compare Variants", callback_data="fbpromo:draft:variants"),
            ],
            [
                InlineKeyboardButton(text="💾 Save Campaign Draft", callback_data="fbpromo:draft:savecampaign"),
            ],
            [
                InlineKeyboardButton(text="💬 Refine Draft", callback_data="fbpromo:draft:refine"),
                InlineKeyboardButton(text="🔁 Regenerate", callback_data="fbpromo:draft:regenerate"),
            ],
            [
                InlineKeyboardButton(text="📋 Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_draft_v4_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Premium", callback_data="fbpromo:draft:preset:premium"),
                InlineKeyboardButton(text="Shorter", callback_data="fbpromo:draft:preset:shorter"),
            ],
            [
                InlineKeyboardButton(text="Urgent", callback_data="fbpromo:draft:preset:urgent"),
            ],
            [
                InlineKeyboardButton(text="Minimal Visual", callback_data="fbpromo:image:preset:minimal"),
                InlineKeyboardButton(text="Lifestyle Visual", callback_data="fbpromo:image:preset:lifestyle"),
            ],
            [
                InlineKeyboardButton(text="Sale Visual", callback_data="fbpromo:image:preset:sale"),
            ],
            [
                InlineKeyboardButton(text="Compare Variants", callback_data="fbpromo:draft:variants"),
            ],
            [
                InlineKeyboardButton(text="Preview Image Generation", callback_data="fbpromo:image:preview"),
            ],
            [
                InlineKeyboardButton(text="Save Campaign Draft", callback_data="fbpromo:draft:savecampaign"),
            ],
            [
                InlineKeyboardButton(text="Refine Draft", callback_data="fbpromo:draft:refine"),
                InlineKeyboardButton(text="Regenerate", callback_data="fbpromo:draft:regenerate"),
            ],
            [
                InlineKeyboardButton(text="Working Plan", callback_data="fbpromo:plan"),
                InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_image_preview_keyboard(can_confirm: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_confirm:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Confirm Use 1 Image Quota",
                    callback_data="fbpromo:image:confirm",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Back To Draft", callback_data="fbpromo:draft:show")])
    rows.append([InlineKeyboardButton(text="Cancel", callback_data="section:Automation:Facebook Promo AI")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_campaigns_keyboard(campaigns: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, title in campaigns[:10]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=title[:32],
                    callback_data=f"fbpromo:campaign:{index}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🚀 Ready Queue", callback_data="fbpromo:readyqueue")])
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI")])
    rows.append([InlineKeyboardButton(text="Published History", callback_data="fbpromo:published")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_facebook_promo_campaign_detail_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve For Publish", callback_data=f"fbpromo:campaignapprove:{index}"),
            ],
            [
                InlineKeyboardButton(text="↩️ Load Back To Draft", callback_data=f"fbpromo:campaignload:{index}"),
            ],
            [
                InlineKeyboardButton(text="📚 Saved Campaigns", callback_data="fbpromo:campaigns"),
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_ready_queue_keyboard(campaigns: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, title in campaigns[:10]:
        rows.append([InlineKeyboardButton(text=title[:32], callback_data=f"fbpromo:campaign:{index}")])
    rows.append([InlineKeyboardButton(text="Saved Campaigns", callback_data="fbpromo:campaigns")])
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_published_history_keyboard(campaigns: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, title in campaigns[:10]:
        rows.append([InlineKeyboardButton(text=title[:32], callback_data=f"fbpromo:campaign:{index}")])
    rows.append([InlineKeyboardButton(text="Saved Campaigns", callback_data="fbpromo:campaigns")])
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_campaigns_v2_keyboard(campaigns: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, title in campaigns[:10]:
        rows.append([InlineKeyboardButton(text=title[:40], callback_data=f"fbpromo:campaign:{index}")])
    rows.append(
        [
            InlineKeyboardButton(text="Ready Queue", callback_data="fbpromo:readyqueue"),
            InlineKeyboardButton(text="Published History", callback_data="fbpromo:published"),
        ]
    )
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_facebook_promo_ready_campaign_detail_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Dry Run Publish", callback_data=f"fbpromo:publishdry:{index}"),
                InlineKeyboardButton(text="Publish Now", callback_data=f"fbpromo:publishnow:{index}"),
            ],
            [InlineKeyboardButton(text="Move Back To Draft", callback_data=f"fbpromo:campaigndraft:{index}")],
            [InlineKeyboardButton(text="Load Back To Draft", callback_data=f"fbpromo:campaignload:{index}")],
            [
                InlineKeyboardButton(text="Saved Campaigns", callback_data="fbpromo:campaigns"),
                InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_facebook_promo_publish_confirm_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Confirm Live Publish", callback_data=f"fbpromo:publishconfirm:{index}")],
            [InlineKeyboardButton(text="Dry Run Again", callback_data=f"fbpromo:publishdry:{index}")],
            [InlineKeyboardButton(text="Cancel", callback_data=f"fbpromo:campaign:{index}")],
        ]
    )


def build_facebook_promo_published_campaign_detail_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Load Back To Draft", callback_data=f"fbpromo:campaignload:{index}")],
            [
                InlineKeyboardButton(text="Saved Campaigns", callback_data="fbpromo:campaigns"),
                InlineKeyboardButton(text="Back", callback_data="section:Automation:Facebook Promo AI"),
            ],
        ]
    )


def build_pending_entities_keyboard(section: str, items: list[tuple[int, str, str | None]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entity_id, identifier, title in items[:15]:
        label = title or identifier
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"reviewopen:{section}:{entity_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ Back", callback_data=f"section:{section}:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_entity_list_keyboard(
    section: str,
    items: list[tuple[int, str, str | None]],
    offset: int = 0,
    page_size: int = 12,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    page_items = items[offset : offset + page_size]
    for _, identifier, title in page_items:
        label = title or identifier
        rows.append([InlineKeyboardButton(text=label[:32], callback_data="noop:list")])

    nav_row: list[InlineKeyboardButton] = []
    if offset > 0:
        prev_offset = max(offset - page_size, 0)
        nav_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"listpage:entity:{section}:{prev_offset}")
        )
    if offset + page_size < len(items):
        next_offset = offset + page_size
        nav_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"listpage:entity:{section}:{next_offset}")
        )
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🏠 Home", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_entity_review_keyboard(section: str, entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Allow",
                    callback_data=f"entity:{section}:{entity_id}:ACTIVE",
                ),
                InlineKeyboardButton(
                    text="🚫 Ignore",
                    callback_data=f"entity:{section}:{entity_id}:IGNORED",
                ),
                InlineKeyboardButton(
                    text="⛔ Block",
                    callback_data=f"entity:{section}:{entity_id}:BLOCKED",
                ),
            ],
        ]
    )


def build_channel_post_keyboard(
    channels: list[tuple[int, str, str | None, bool, bool]],
    filter_mode: str = "all",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="⭐ Favorites" if filter_mode != "favorites" else "✅ Favorites",
                callback_data="picker:post:favorites",
            ),
            InlineKeyboardButton(
                text="📋 All" if filter_mode != "all" else "✅ All",
                callback_data="picker:post:all",
            ),
            InlineKeyboardButton(
                text="🔎 Search",
                callback_data="pickersearch:post",
            ),
        ]
    ]
    rows.extend(_build_quick_target_rows(channels, "post:channel"))
    for entity_id, identifier, title, is_favorite, is_recent in channels[:10]:
        label = title or identifier
        prefix = ""
        if is_favorite:
            prefix += "⭐ "
        elif is_recent:
            prefix += "🕘 "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{label[:28]}",
                    callback_data=f"post:channel:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="★" if is_favorite else "☆",
                    callback_data=f"favorite:post:{entity_id}",
                ),
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Channels:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_channel_schedule_keyboard(
    channels: list[tuple[int, str, str | None, bool, bool]],
    filter_mode: str = "all",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="⭐ Favorites" if filter_mode != "favorites" else "✅ Favorites",
                callback_data="picker:schedule:favorites",
            ),
            InlineKeyboardButton(
                text="📋 All" if filter_mode != "all" else "✅ All",
                callback_data="picker:schedule:all",
            ),
            InlineKeyboardButton(
                text="🔎 Search",
                callback_data="pickersearch:schedule",
            ),
        ]
    ]
    rows.extend(_build_quick_target_rows(channels, "schedule:channel"))
    for entity_id, identifier, title, is_favorite, is_recent in channels[:10]:
        label = title or identifier
        prefix = ""
        if is_favorite:
            prefix += "⭐ "
        elif is_recent:
            prefix += "🕘 "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{label[:28]}",
                    callback_data=f"schedule:channel:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="★" if is_favorite else "☆",
                    callback_data=f"favorite:schedule:{entity_id}",
                ),
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Channels:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_schedule_mode_keyboard(entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Exact", callback_data=f"schedulemode:{entity_id}:EXACT"),
                InlineKeyboardButton(text="🔁 Daily", callback_data=f"schedulemode:{entity_id}:DAILY"),
            ],
            [
                InlineKeyboardButton(text="📆 Weekly", callback_data=f"schedulemode:{entity_id}:WEEKLY"),
                InlineKeyboardButton(text="🗓️ Monthly", callback_data=f"schedulemode:{entity_id}:MONTHLY"),
            ],
            [
                InlineKeyboardButton(text="💼 Workdays", callback_data=f"schedulemode:{entity_id}:WORKDAYS"),
                InlineKeyboardButton(text="🌴 Weekend", callback_data=f"schedulemode:{entity_id}:WEEKEND"),
            ],
            [
                InlineKeyboardButton(text="⏳ Delay", callback_data=f"schedulemode:{entity_id}:DELAY"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data="section:Channels:Schedule"),
            ],
        ]
    )


def build_schedule_weekday_keyboard(entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Sat", callback_data=f"scheduleweekday:{entity_id}:5"),
                InlineKeyboardButton(text="Sun", callback_data=f"scheduleweekday:{entity_id}:6"),
                InlineKeyboardButton(text="Mon", callback_data=f"scheduleweekday:{entity_id}:0"),
                InlineKeyboardButton(text="Tue", callback_data=f"scheduleweekday:{entity_id}:1"),
            ],
            [
                InlineKeyboardButton(text="Wed", callback_data=f"scheduleweekday:{entity_id}:2"),
                InlineKeyboardButton(text="Thu", callback_data=f"scheduleweekday:{entity_id}:3"),
                InlineKeyboardButton(text="Fri", callback_data=f"scheduleweekday:{entity_id}:4"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data=f"schedule:channel:{entity_id}"),
            ],
        ]
    )


def build_schedule_monthday_keyboard(entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"schedulemonthday:{entity_id}:1"),
                InlineKeyboardButton(text="5", callback_data=f"schedulemonthday:{entity_id}:5"),
                InlineKeyboardButton(text="10", callback_data=f"schedulemonthday:{entity_id}:10"),
            ],
            [
                InlineKeyboardButton(text="15", callback_data=f"schedulemonthday:{entity_id}:15"),
                InlineKeyboardButton(text="20", callback_data=f"schedulemonthday:{entity_id}:20"),
                InlineKeyboardButton(text="Last", callback_data=f"schedulemonthday:{entity_id}:31"),
            ],
            [
                InlineKeyboardButton(text="◀️ Back", callback_data=f"schedule:channel:{entity_id}"),
            ],
        ]
    )


def build_schedule_time_shortcuts_keyboard(options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(options), 2):
        chunk = options[index : index + 2]
        rows.append(
            [
                InlineKeyboardButton(text=label, callback_data=f"schedulequick:{token}")
                for label, token in chunk
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"),
            InlineKeyboardButton(text="◀️ Back", callback_data="section:Channels:Schedule"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_schedule_list_keyboard(items: list[tuple[int, str, str | None, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for schedule_id, label, recurrence_key, status in items[:10]:
        action_row: list[InlineKeyboardButton] = []
        if recurrence_key and status == "PENDING":
            action_row.append(
                InlineKeyboardButton(
                    text=f"Pause {label[:16]}",
                    callback_data=f"schedule:pause:{schedule_id}",
                )
            )
            action_row.append(
                InlineKeyboardButton(
                    text="Skip Next",
                    callback_data=f"schedule:skip:{schedule_id}",
                )
            )
        elif recurrence_key and status == "PAUSED":
            action_row.append(
                InlineKeyboardButton(
                    text=f"Resume {label[:16]}",
                    callback_data=f"schedule:resume:{schedule_id}",
                )
            )

        if action_row:
            rows.append(action_row)

        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Cancel {label[:24]}",
                    callback_data=f"schedule:cancel:{schedule_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Channels:Schedule")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_schedule_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="scheduleconfirm:save"),
                InlineKeyboardButton(text="✏️ Edit Time", callback_data="scheduleconfirm:time"),
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="scheduleconfirm:cancel"),
            ],
        ]
    )


def build_post_confirm_keyboard(kind: str) -> InlineKeyboardMarkup:
    action_prefix = "postconfirm" if kind == "post" else "broadcastconfirm"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"{action_prefix}:send"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"{action_prefix}:cancel"),
            ]
        ]
    )


def build_automation_template_keyboard(templates: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for template_key, label in templates:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"automation:create:{template_key}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Automation:Templates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_automation_rules_keyboard(rules: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for rule_id, label, status in rules[:15]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{label[:24]} [{status}]",
                    callback_data=f"automation:detail:{rule_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Automation:Rules")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_automation_rule_detail_keyboard(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "Pause" if is_active else "Activate"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_label,
                    callback_data=f"automation:toggle:{rule_id}",
                ),
                InlineKeyboardButton(
                    text="Delete",
                    callback_data=f"automation:delete:{rule_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data="section:Automation:Rules",
                )
            ],
        ]
    )


def build_group_moderation_keyboard(groups: list[tuple[int, str, str | None]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entity_id, identifier, title in groups[:15]:
        label = title or identifier
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"group:moderation:{entity_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Groups:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_group_control_keyboard(entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Lock",
                    callback_data=f"group:lock:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="Unlock",
                    callback_data=f"group:unlock:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Refresh",
                    callback_data=f"group:moderation:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="section:Groups:Moderation"),
            ],
        ]
    )


def build_group_warning_keyboard(groups: list[tuple[int, str, str | None]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entity_id, identifier, title in groups[:15]:
        label = title or identifier
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"group:warnings:{entity_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Groups:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_group_warning_control_keyboard(entity_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Refresh",
                    callback_data=f"group:warnings:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="Reset All",
                    callback_data=f"groupwarn:reset:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="section:Groups:Warnings"),
            ],
        ]
    )


def build_group_filter_keyboard(groups: list[tuple[int, str, str | None]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entity_id, identifier, title in groups[:15]:
        label = title or identifier
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"group:filters:{entity_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Groups:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_group_filter_control_keyboard(entity_id: int, anti_link_enabled: bool, bad_word_enabled: bool) -> InlineKeyboardMarkup:
    anti_label = "Anti-Link: ON" if anti_link_enabled else "Anti-Link: OFF"
    bad_label = "Bad-Words: ON" if bad_word_enabled else "Bad-Words: OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=anti_label,
                    callback_data=f"groupfilter:antilink:{entity_id}",
                ),
                InlineKeyboardButton(
                    text=bad_label,
                    callback_data=f"groupfilter:badword:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Refresh",
                    callback_data=f"group:filters:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="Clear Custom",
                    callback_data=f"groupfilter:clearbad:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="section:Groups:Filters"),
            ],
        ]
    )


def build_group_welcome_keyboard(groups: list[tuple[int, str, str | None]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entity_id, identifier, title in groups[:15]:
        label = title or identifier
        rows.append(
            [
                InlineKeyboardButton(
                    text=label[:32],
                    callback_data=f"group:welcome:{entity_id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Groups:View")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_group_welcome_control_keyboard(entity_id: int, welcome_enabled: bool, join_log_enabled: bool) -> InlineKeyboardMarkup:
    welcome_label = "Welcome: ON" if welcome_enabled else "Welcome: OFF"
    join_log_label = "Join Logs: ON" if join_log_enabled else "Join Logs: OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=welcome_label,
                    callback_data=f"groupwelcome:toggle:{entity_id}",
                ),
                InlineKeyboardButton(
                    text=join_log_label,
                    callback_data=f"groupwelcome:logs:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Refresh",
                    callback_data=f"group:welcome:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="Clear Template",
                    callback_data=f"groupwelcome:clear:{entity_id}",
                ),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="section:Groups:Welcome"),
            ],
        ]
    )


def build_broadcast_select_keyboard(
    channels: list[tuple[int, str, str | None, bool, bool]],
    selected_ids: set[int],
    filter_mode: str = "all",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="⭐ Favorites" if filter_mode != "favorites" else "✅ Favorites",
                callback_data="picker:broadcast:favorites",
            ),
            InlineKeyboardButton(
                text="📋 All" if filter_mode != "all" else "✅ All",
                callback_data="picker:broadcast:all",
            ),
            InlineKeyboardButton(
                text="🔎 Search",
                callback_data="pickersearch:broadcast",
            ),
        ]
    ]
    rows.extend(_build_quick_target_rows(channels, "broadcast:toggle"))
    for entity_id, identifier, title, is_favorite, is_recent in channels[:20]:
        label = title or identifier
        mark = "[x]" if entity_id in selected_ids else "[ ]"
        prefix = ""
        if is_favorite:
            prefix += "⭐ "
        elif is_recent:
            prefix += "🕘 "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {prefix}{label[:24]}",
                    callback_data=f"broadcast:toggle:{entity_id}",
                ),
                InlineKeyboardButton(
                    text="★" if is_favorite else "☆",
                    callback_data=f"favorite:broadcast:{entity_id}",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(text="Compose", callback_data="broadcast:compose"),
            InlineKeyboardButton(text="Clear", callback_data="broadcast:clear"),
        ]
    )
    rows.append([InlineKeyboardButton(text="Back", callback_data="section:Broadcast:Targets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_access_request_review_keyboard(telegram_user_id: int, role_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Approve",
                    callback_data=f"accessreq:{telegram_user_id}:{role_key}:APPROVED",
                ),
                InlineKeyboardButton(
                    text="Reject",
                    callback_data=f"accessreq:{telegram_user_id}:{role_key}:REJECTED",
                ),
            ],
        ]
    )


def build_bot_status_keyboard(bots: list[tuple[int, str, str | None, str]]) -> InlineKeyboardMarkup:
    return build_bot_picker_keyboard("status", bots)


def build_bot_picker_keyboard(
    kind: str,
    bots: list[tuple[int, str, str | None, str]],
    offset: int = 0,
    page_size: int = 12,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    page_items = bots[offset : offset + page_size]
    for bot_id, bot_username, display_name, status in page_items:
        label = display_name or bot_username
        if kind == "status":
            callback_data = f"bot:detail:{bot_id}"
            text = f"{label[:22]} [{status[:8]}]"
        elif kind == "logs":
            callback_data = f"bot:logs:{bot_id}"
            text = f"{label[:24]} logs"
        else:
            callback_data = f"bot:config:{bot_id}"
            text = f"{label[:24]} config"
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    nav_row: list[InlineKeyboardButton] = []
    if offset > 0:
        prev_offset = max(offset - page_size, 0)
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"listpage:bot:{kind}:{prev_offset}"))
    if offset + page_size < len(bots):
        next_offset = offset + page_size
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"listpage:bot:{kind}:{next_offset}"))
    if nav_row:
        rows.append(nav_row)

    back_target = {
        "status": "section:Bots:Status",
        "logs": "section:Bots:Logs",
        "configs": "section:Bots:Settings",
    }[kind]
    rows.append([InlineKeyboardButton(text="Back", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_bot_logs_keyboard(bots: list[tuple[int, str, str | None, str]]) -> InlineKeyboardMarkup:
    return build_bot_picker_keyboard("logs", bots)


def build_bot_configs_keyboard(bots: list[tuple[int, str, str | None, str]]) -> InlineKeyboardMarkup:
    return build_bot_picker_keyboard("configs", bots)


def build_bot_detail_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Refresh Status",
                    callback_data=f"bot:refresh:{bot_id}",
                ),
                InlineKeyboardButton(
                    text="Run Action",
                    callback_data=f"bot:action:{bot_id}",
                ),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="section:Bots:Status"),
            ],
        ]
    )
