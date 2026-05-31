from __future__ import annotations

from urllib.parse import quote, unquote


def safe_next_url(next_url: str | None) -> str:
    value = unquote((next_url or "").strip()) or "/dashboard"
    if not value.startswith("/") or value.startswith("//"):
        return "/dashboard"
    return value


def reauth_redirect_target(query: str = "", status_filter: str = "ALL") -> str:
    next_url = f"/dashboard?q={query}&status={status_filter}"
    return f"/dashboard/reauth?next={quote(next_url, safe='/?=&')}"


def build_dashboard_redirect_url(
    notice: str | None = None,
    error: str | None = None,
    query: str = "",
    status_filter: str = "ALL",
) -> str:
    url = f"/dashboard?q={quote(query)}&status={quote(status_filter)}"
    if notice:
        url += f"&notice={quote(notice)}"
    if error:
        url += f"&error={quote(error)}"
    return url
