from __future__ import annotations

import unittest

from app.web_safe_helpers import (
    build_dashboard_redirect_url,
    reauth_redirect_target,
    safe_next_url,
)


class WebSafeHelpersTests(unittest.TestCase):
    def test_safe_next_url_allows_local_dashboard_path(self) -> None:
        self.assertEqual(
            safe_next_url("/dashboard?q=test&status=ACTIVE"),
            "/dashboard?q=test&status=ACTIVE",
        )

    def test_safe_next_url_blocks_external_target(self) -> None:
        self.assertEqual(safe_next_url("https://evil.example"), "/dashboard")
        self.assertEqual(safe_next_url("//evil.example"), "/dashboard")

    def test_reauth_redirect_target(self) -> None:
        self.assertEqual(
            reauth_redirect_target("abc", "PENDING"),
            "/dashboard/reauth?next=/dashboard?q=abc&status=PENDING",
        )

    def test_build_dashboard_redirect_url(self) -> None:
        self.assertEqual(
            build_dashboard_redirect_url(notice="done", query="abc", status_filter="FAILED"),
            "/dashboard?q=abc&status=FAILED&notice=done",
        )


if __name__ == "__main__":
    unittest.main()
