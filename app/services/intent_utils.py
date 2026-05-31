from __future__ import annotations


def parse_natural_intent(text: str | None) -> tuple[str, str] | None:
    if not text:
        return None

    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None

    direct_map = {
        "home": ("section", "Home"),
        "create": ("section", "Create"),
        "status": ("section", "Status"),
        "more": ("section", "More"),
        "channels": ("section", "Channels"),
        "groups": ("section", "Groups"),
        "bots": ("section", "Bots"),
        "reports": ("section", "Reports"),
        "automation": ("section", "Automation"),
        "settings": ("section", "Settings"),
        "post": ("flow", "post"),
        "new post": ("flow", "post"),
        "quick post": ("flow", "post"),
        "schedule": ("flow", "schedule"),
        "new schedule": ("flow", "schedule"),
        "quick schedule": ("flow", "schedule"),
        "broadcast": ("flow", "broadcast"),
        "send broadcast": ("flow", "broadcast"),
        "review": ("flow", "review"),
        "pending": ("flow", "review"),
        "review pending": ("flow", "review"),
        "alerts": ("flow", "alerts"),
    }
    if normalized in direct_map:
        return direct_map[normalized]

    if "review" in normalized and "pending" in normalized:
        return ("flow", "review")
    if "quick" in normalized and "post" in normalized:
        return ("flow", "post")
    if "quick" in normalized and "schedule" in normalized:
        return ("flow", "schedule")
    if "send" in normalized and "broadcast" in normalized:
        return ("flow", "broadcast")

    return None


def build_intent_fallback_text(text: str | None) -> str:
    sample = (text or "").strip()
    if sample:
        sample_line = f"`{sample}` diye exact intent bujhte pari nai.\n\n"
    else:
        sample_line = ""

    return (
        "🤝 I can help faster if you use a simple action word.\n\n"
        f"{sample_line}"
        "Try one of these:\n"
        "- `post`\n"
        "- `schedule`\n"
        "- `broadcast`\n"
        "- `review pending`\n"
        "- `alerts`\n"
        "- `bots`\n\n"
        "Or use the menu buttons below."
    )
