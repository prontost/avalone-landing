"""User data access for Avalone Finance.

This repository owns the `users` table in the unified Avalone DB.
Finance features are available to every user by default; admin checks are delegated to the portal `admin` role.
It is intentionally decoupled from the request-scoped tenant context; pass
`tenant_id` explicitly from `TenantService`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository
from avalone_core import glossary_db as glossary
import avalone_finance.core.db as _finance_db  # resolve DB_PATH dynamically (tests patch it)

_OWNER_TENANT_ID = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    login          TEXT UNIQUE NOT NULL,
    pwhash         TEXT NOT NULL,
    email          TEXT DEFAULT '',
    email_verified INTEGER DEFAULT 0,
    verify_code    TEXT DEFAULT '',
    verify_sent    TEXT DEFAULT '',
    reset_token    TEXT DEFAULT '',
    reset_expires  TEXT DEFAULT '',
    created_at     TEXT NOT NULL
);
"""


class UserRepository(Repository):
    """Data access for users and instance admins."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_finance_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.executescript(_SCHEMA)
        self._migrate_users_columns(con)
        return con

    @staticmethod
    def _migrate_users_columns(con: sqlite3.Connection) -> None:
        """Idempotently add columns that older schemas may be missing."""
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        except sqlite3.OperationalError:
            return
        additions = {
            "email_verified": "INTEGER DEFAULT 0",
            "verify_code": "TEXT DEFAULT ''",
            "verify_sent": "TEXT DEFAULT ''",
            "reset_token": "TEXT DEFAULT ''",
            "reset_expires": "TEXT DEFAULT ''",
            "referral_code": "TEXT",
            "referred_by": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        }
        for col, dtype in additions.items():
            if col not in cols:
                try:
                    con.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                except sqlite3.OperationalError:
                    pass
        try:
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)"
            )
        except sqlite3.OperationalError:
            pass

    # --- пароли (PBKDF2, stdlib) ---
    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return f"pbkdf2$200000${salt.hex()}${dk.hex()}"

    def verify_password(self, password: str, stored: str) -> bool:
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

    # --- пользователи ---
    def create(self, login: str, password: str, email: str = "") -> int:
        login = login.strip().lower()
        if not login or not password:
            raise ValueError(glossary.t("error_login_password_required", lang="ru"))
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO users (login, pwhash, email, created_at) VALUES (?,?,?,?)",
                (login, self.hash_password(password), email.strip().lower(), now),
            )
            return cur.lastrowid

    def get_by_login(self, login: str) -> dict | None:
        with self._conn() as con:
            r = con.execute(
                "SELECT id, login, pwhash, email FROM users WHERE login=?",
                (login.strip().lower(),),
            ).fetchone()
        if not r:
            return None
        return {"id": r[0], "login": r[1], "pwhash": r[2], "email": r[3]}

    def get_user(self, tenant_id: int) -> dict | None:
        with self._conn() as con:
            r = con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users WHERE id=?",
                (tenant_id,),
            ).fetchone()
        if not r:
            return None
        return {"id": r[0], "login": r[1], "email": r[2], "email_verified": r[3], "created_at": r[4]}

    def get_user_by_login(self, login: str) -> dict | None:
        login = login.strip().lower()
        with self._conn() as con:
            r = con.execute(
                "SELECT id, login, email, created_at FROM users WHERE login=?",
                (login,),
            ).fetchone()
        if not r:
            return None
        return {"id": r[0], "login": r[1], "email": r[2], "created_at": r[3]}

    def login_taken(self, login: str) -> bool:
        return self.get_by_login(login) is not None

    def count_users(self) -> int:
        with self._conn() as con:
            return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def all_ids(self) -> list[int]:
        with self._conn() as con:
            return [r[0] for r in con.execute("SELECT id FROM users ORDER BY id")]

    def list_users(self) -> list[dict]:
        """All users with their per-tenant entry counts (admin aggregate)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT u.id, u.login, u.email, u.created_at, "
                "(SELECT COUNT(*) FROM money_led_entries e WHERE e.tenant=u.id) AS entries "
                "FROM users u ORDER BY u.id"
            ).fetchall()
        return [
            {"id": r[0], "login": r[1], "email": r[2], "created_at": r[3], "entries": r[4]}
            for r in rows
        ]

    def count_entries(self) -> int:
        """Total entries across all tenants (admin aggregate)."""
        with self._conn() as con:
            row = con.execute("SELECT COUNT(*) FROM money_led_entries").fetchone()
        return row[0] if row else 0

    def accounts_for_email(self, email: str) -> list[dict]:
        email = (email or "").strip().lower()
        if not email:
            return []
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, login, email FROM users WHERE email=? ORDER BY id",
                (email,),
            ).fetchall()
        return [{"id": r[0], "login": r[1], "email": r[2]} for r in rows]

    def change_password(self, tenant_id: int, old_pw: str, new_pw: str) -> bool:
        with self._conn() as con:
            r = con.execute("SELECT pwhash FROM users WHERE id=?", (tenant_id,)).fetchone()
            if not r or not self.verify_password(old_pw, r[0]):
                return False
            con.execute(
                "UPDATE users SET pwhash=? WHERE id=?",
                (self.hash_password(new_pw), tenant_id),
            )
        return True

    def set_password(self, tenant_id: int, new_pw: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET pwhash=? WHERE id=?",
                (self.hash_password(new_pw), tenant_id),
            )

    def set_email(self, tenant_id: int, email: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET email=?, email_verified=0 WHERE id=?",
                (email.strip().lower(), tenant_id),
            )

    def set_verify_code(self, tenant_id: int, code: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            con.execute(
                "UPDATE users SET verify_code=?, verify_sent=? WHERE id=?",
                (code, now, tenant_id),
            )

    _VERIFY_TTL_SECONDS = 30 * 60

    def check_verify_code(self, tenant_id: int, code: str) -> bool:
        code = (code or "").strip()
        if not code:
            return False
        now = datetime.now(timezone.utc)
        with self._conn() as con:
            r = con.execute(
                "SELECT verify_code, verify_sent FROM users WHERE id=?",
                (tenant_id,),
            ).fetchone()
            if not r or not r[0] or not hmac.compare_digest(r[0], code):
                return False
            sent = r[1]
            if not sent:
                return False
            try:
                sent_dt = datetime.fromisoformat(sent)
            except Exception:
                return False
            if (now - sent_dt).total_seconds() > self._VERIFY_TTL_SECONDS:
                return False
            con.execute(
                "UPDATE users SET email_verified=1, verify_code='', verify_sent='' WHERE id=?",
                (tenant_id,),
            )
        return True

    def set_reset_token(self, tenant_id: int, token: str, expires_iso: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token=?, reset_expires=? WHERE id=?",
                (token, expires_iso, tenant_id),
            )

    def consume_reset_token(self, token: str) -> int | None:
        token = (token or "").strip()
        if not token:
            return None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            r = con.execute(
                "SELECT id, reset_expires FROM users WHERE reset_token=?", (token,)
            ).fetchone()
            if not r or not r[1] or r[1] < now:
                return None
            con.execute(
                "UPDATE users SET reset_token='', reset_expires='' WHERE id=?",
                (r[0],),
            )
        return r[0]

    def delete_user(self, tenant_id: int) -> None:
        with self._conn() as con:
            for tbl in (
                "money_led_accounts",
                "money_led_entries",
                "money_led_lines",
                "money_led_seq",
                "money_money_accounts",
                "money_user_settings",
                "money_catalog_i18n",
                "money_entry_meta",
                "money_slept_entries",
                "money_lexicon",
                "money_user_apps",
                "money_notifications",
            ):
                try:
                    con.execute(f"DELETE FROM {tbl} WHERE tenant=?", (tenant_id,))
                except sqlite3.OperationalError:
                    pass
            con.execute("DELETE FROM users WHERE id=?", (tenant_id,))

    def ensure_owner(self, login: str, password: str) -> int:
        with self._conn() as con:
            exists = con.execute("SELECT id FROM users WHERE id=?", (_OWNER_TENANT_ID,)).fetchone()
            if exists:
                return _OWNER_TENANT_ID
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            con.execute(
                "INSERT INTO users (id, login, pwhash, email, created_at) VALUES (?,?,?,?,?)",
                (
                    _OWNER_TENANT_ID,
                    login.strip().lower(),
                    self.hash_password(password),
                    "",
                    now,
                ),
            )
        return _OWNER_TENANT_ID
