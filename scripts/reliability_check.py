from __future__ import annotations

import argparse
import compileall
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
ENV_FILE = REPO_ROOT / ".env"


def check_compile() -> tuple[bool, str]:
    ok = compileall.compile_dir(str(APP_DIR), force=True, quiet=1)
    return ok, "Python compile sweep"


def _load_env_value(key: str) -> str | None:
    direct = os.getenv(key)
    if direct:
        return direct
    if not ENV_FILE.exists():
        return None
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_key, env_value = line.split("=", 1)
        if env_key.strip() == key:
            return env_value.strip().strip('"').strip("'")
    return None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_status(url: str, timeout: int = 10, follow_redirects: bool = True) -> tuple[int | None, str | None]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "everithing_manager-reliability-check/1.0"},
    )
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.getcode(), None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:
        return None, str(exc)


def check_http(url: str, expected_status: int = 200, timeout: int = 10, follow_redirects: bool = True) -> tuple[bool, str]:
    status, error = _request_status(url, timeout=timeout, follow_redirects=follow_redirects)
    if error:
        return False, f"{url} -> error: {error}"
    if status != expected_status:
        return False, f"{url} -> expected {expected_status}, got {status}"
    return True, f"{url} -> {status}"


def check_bot_api(bot_token: str | None) -> tuple[bool, str]:
    if not bot_token:
        return True, "Telegram bot API check skipped (BOT_TOKEN not found)"
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "everithing_manager-reliability-check/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return False, f"Telegram getMe -> error: {exc}"

    if not payload.get("ok"):
        return False, f"Telegram getMe -> unexpected payload: {payload}"
    result = payload.get("result") or {}
    username = result.get("username") or "-"
    bot_id = result.get("id") or "-"
    return True, f"Telegram getMe -> ok | @{username} | id={bot_id}"


def run_checks(public_url: str, local_url: str | None, skip_local_health: bool) -> int:
    checks: list[tuple[bool, str]] = []
    checks.append(check_compile())
    checks.append(check_bot_api(_load_env_value("BOT_TOKEN")))
    checks.append(check_http(f"{public_url.rstrip('/')}"))
    checks.append(check_http(f"{public_url.rstrip('/')}/healthz"))
    checks.append(check_http(f"{public_url.rstrip('/')}/dashboard", expected_status=302, follow_redirects=False))
    checks.append(check_http(f"{public_url.rstrip('/')}/api/report", expected_status=401, follow_redirects=False))
    if not skip_local_health and local_url:
        checks.append(check_http(f"{local_url.rstrip('/')}"))
        checks.append(check_http(f"{local_url.rstrip('/')}/healthz"))
        checks.append(check_http(f"{local_url.rstrip('/')}/dashboard", expected_status=302, follow_redirects=False))
        checks.append(check_http(f"{local_url.rstrip('/')}/api/report", expected_status=401, follow_redirects=False))

    failed = 0
    for ok, message in checks:
        prefix = "[PASS]" if ok else "[FAIL]"
        print(f"{prefix} {message}")
        if not ok:
            failed += 1

    if failed:
        print(f"\nResult: {failed} check(s) failed.")
        return 1

    print("\nResult: all reliability checks passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight reliability checks for everithing_manager.")
    parser.add_argument(
        "--public-url",
        default="https://empanel.leono.shop",
        help="Public dashboard base URL.",
    )
    parser.add_argument(
        "--local-url",
        default="http://127.0.0.1:8080",
        help="Local dashboard base URL.",
    )
    parser.add_argument(
        "--skip-local-health",
        action="store_true",
        help="Skip the local dashboard health check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_checks(args.public_url, args.local_url, args.skip_local_health)


if __name__ == "__main__":
    sys.exit(main())
