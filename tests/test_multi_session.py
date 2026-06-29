"""Tests for Avalone multi-session cookie handling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from avalone_landing.core.auth_service import AuthService
from avalone_landing.web.app import app


def _session_cookie_from(response) -> str:
    set_cookie = response.headers.get("set-cookie") or ""
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("avalone_sessions="):
            return part.split("=", 1)[1]
    return ""


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    return AuthService()


def test_register_keeps_previous_session(client, auth):
    """Registering a second account while logged in must keep the first session."""
    r1 = client.post("/api/auth/register", json={
        "login": "first_user",
        "password": "Pass1234!",
        "password2": "Pass1234!",
    })
    assert r1.status_code == 200
    cookie1 = _session_cookie_from(r1)
    assert cookie1

    # Simulate the browser sending the existing session cookie to the register endpoint.
    client.headers["Cookie"] = f"avalone_sessions={cookie1}"
    r2 = client.post("/api/auth/register", json={
        "login": "second_user",
        "password": "Pass1234!",
        "password2": "Pass1234!",
    })
    assert r2.status_code == 200
    cookie2 = _session_cookie_from(r2)
    assert cookie2

    active, sessions = auth._parse(cookie2)
    uids = {s["uid"] for s in sessions}
    assert active in uids
    assert len(sessions) == 2
    assert len(uids) == 2


def test_login_keeps_previous_session(client, auth):
    """Logging into a second account while logged in must keep the first session."""
    r1 = client.post("/api/auth/register", json={
        "login": "alpha",
        "password": "Pass1234!",
        "password2": "Pass1234!",
    })
    cookie1 = _session_cookie_from(r1)

    client.post("/api/auth/register", json={
        "login": "beta",
        "password": "Pass1234!",
        "password2": "Pass1234!",
    })

    client.headers["Cookie"] = f"avalone_sessions={cookie1}"
    r2 = client.post("/api/auth/login", json={
        "login": "beta",
        "password": "Pass1234!",
    })
    cookie2 = _session_cookie_from(r2)

    active, sessions = auth._parse(cookie2)
    uids = {s["uid"] for s in sessions}
    assert active in uids
    assert len(sessions) == 2
    assert len(uids) == 2
