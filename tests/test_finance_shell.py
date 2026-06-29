"""Tests that Avalone Finance renders the shared shell with session context."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.user_service import UserService
from avalone_landing.web.app import app


def _issue_two_session_cookie(uids: tuple[int, int]) -> str:
    """Create a signed avalone_sessions cookie with two sessions by uid."""
    auth = AuthService()
    from fastapi import Response

    resp = Response()
    # Use a production-like request so the cookie domain matches the TestClient.
    req = type(
        "R",
        (),
        {
            "url": type("U", (), {"hostname": "avalone.online", "scheme": "https"})(),
            "cookies": {},
        },
    )()
    auth._set_cookie(
        req,
        resp,
        active=uids[1],
        sessions=[
            {"uid": uids[0], "at": "2026-06-29T01:00:00+00:00"},
            {"uid": uids[1], "at": "2026-06-29T01:00:01+00:00"},
        ],
    )
    set_cookie = resp.headers["set-cookie"]
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("avalone_sessions="):
            return part.split("=", 1)[1]
    raise RuntimeError("no avalone_sessions cookie in response")


@pytest.fixture
def client():
    return TestClient(app, base_url="https://avalone.online")


def test_finance_page_shows_profile_switcher_when_multiple_sessions(client):
    """The shared shell rendered inside /finance must know about all sessions."""
    # Seed the unified users table so TenantService can resolve session users.
    user_service = UserService()
    user_service.create_user("shell_alpha", "Pass1234!")
    user_service.create_user("shell_beta", "Pass1234!")
    uid_alpha = user_service._repo.get_by_login_or_email("shell_alpha").id
    uid_beta = user_service._repo.get_by_login_or_email("shell_beta").id

    cookie = _issue_two_session_cookie((uid_alpha, uid_beta))
    client.cookies.set("avalone_sessions", cookie, domain="avalone.online", path="/")

    resp = client.get("/finance", follow_redirects=True)
    assert resp.status_code == 200
    assert "avalone-profile-switcher" in resp.text
    assert "shell_alpha" in resp.text
    assert "shell_beta" in resp.text
