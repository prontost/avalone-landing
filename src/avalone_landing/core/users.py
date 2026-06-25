"""Avalone users and password auth.

Lightweight version of Counta's tenant module. Passwords are PBKDF2-HMAC-SHA256
(stdlib only). The session itself is a signed cookie handled by the web layer.
"""

import hashlib
import hmac
import os
import sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone

from avalone_landing.core.db import DB_PATH

_current: ContextVar[int] = ContextVar("user_id", default=0)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    login      TEXT UNIQUE NOT NULL,
    pwhash     TEXT NOT NULL,
    email      TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    return con


def set_current(user_id: int) -> None:
    _current.set(user_id)


def current() -> int:
    return _current.get()


def require_current() -> int:
    uid = _current.get()
    if not uid:
        raise PermissionError("user not authenticated")
    return uid


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2$200000${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, dk_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def create_user(login: str, password: str, email: str = "") -> int:
    login = login.strip().lower()
    if not login or not password:
        raise ValueError("login and password are required")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO users (login, pwhash, email, created_at) VALUES (?, ?, ?, ?)",
            (login, hash_password(password), email.strip().lower(), now),
        )
        return cur.lastrowid


def get_by_login(login: str) -> dict | None:
    with _conn() as con:
        r = con.execute(
            "SELECT id, login, pwhash, email, created_at FROM users WHERE login = ?",
            (login.strip().lower(),),
        ).fetchone()
    if not r:
        return None
    return {"id": r[0], "login": r[1], "pwhash": r[2], "email": r[3], "created_at": r[4]}


def get_user(user_id: int) -> dict | None:
    with _conn() as con:
        r = con.execute(
            "SELECT id, login, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not r:
        return None
    return {"id": r[0], "login": r[1], "email": r[2], "created_at": r[3]}


def authenticate(login: str, password: str) -> int | None:
    u = get_by_login(login)
    if u and verify_password(password, u["pwhash"]):
        return u["id"]
    return None


def login_taken(login: str) -> bool:
    return get_by_login(login) is not None
