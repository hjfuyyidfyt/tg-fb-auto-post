from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


MAIN_MENU_KEYS = (
    "Home",
    "Create",
    "Review",
    "Status",
    "Channels",
    "Groups",
    "Bots",
    "Reports",
    "Automation",
    "Settings",
    "More",
)

MENU_KEY_TO_LABEL = {
    "Home": "🏠 Home",
    "Create": "⚡ Create",
    "Review": "✅ Review",
    "Status": "📊 Status",
    "Channels": "📢 Channels",
    "Groups": "👥 Groups",
    "Bots": "🤖 Bots",
    "Reports": "📋 Reports",
    "Automation": "⚙️ Automation",
    "Settings": "🛠️ Settings",
    "More": "⚙️ More",
}

MENU_LABEL_TO_KEY = {label: key for key, label in MENU_KEY_TO_LABEL.items()}
MAIN_MENU_LABELS = tuple(MENU_LABEL_TO_KEY.keys())


def build_main_menu_layout() -> list[list[str]]:
    return [
        ["Home", "Create"],
        ["Review", "Status"],
        ["Channels", "Groups"],
        ["Bots", "Reports"],
        ["Automation", "Settings"],
        ["More"],
    ]


def normalize_main_menu_label(text: str | None) -> str | None:
    if not text:
        return None
    return MENU_LABEL_TO_KEY.get(text)


def build_main_menu_keyboard(allowed_keys: list[str] | tuple[str, ...] | None = None) -> ReplyKeyboardMarkup:
    visible = set(allowed_keys or MAIN_MENU_KEYS)
    rows = []
    for row in build_main_menu_layout():
        filtered = [label for label in row if label in visible]
        if filtered:
            rows.append([KeyboardButton(text=MENU_KEY_TO_LABEL[label]) for label in filtered])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Choose what you want to do",
    )
