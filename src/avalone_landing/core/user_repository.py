"""User and admin data access for the Avalone portal."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository

from avalone_landing.core.models import User


class UserRepository(Repository):
    """SQL access for the portal `users` and `admins` tables."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database.shared())

    def _conn(self) -> sqlite3.Connection:
        return self._db.connection()

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return f"pbkdf2$200000${salt.hex()}${dk.hex()}"

    @staticmethod
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

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            login=row["login"],
            email=row["email"] or "",
            created_at=row["created_at"],
            email_verified=bool(row["email_verified"]),
        )

    def get_by_id(self, user_id: int) -> User | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        user = self._row_to_user(row)
        user.is_admin = self.is_admin(user_id)
        return user

    def get_by_login_or_email(self, value: str) -> User | None:
        value = value.strip().lower()
        with self._conn() as con:
            row = con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users "
                "WHERE login = ? OR email = ?",
                (value, value),
            ).fetchone()
        if not row:
            return None
        user = self._row_to_user(row)
        user.is_admin = self.is_admin(user.id)
        return user

    def create(self, login: str, password: str, email: str = "") -> int:
        login = login.strip().lower()
        if not login or not password:
            raise ValueError("login and password are required")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO users (login, pwhash, email, created_at) VALUES (?, ?, ?, ?)",
                (login, self.hash_password(password), email.strip().lower(), now),
            )
            return cur.lastrowid or 0

    def update_email(self, user_id: int, email: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET email = ?, email_verified = 0 WHERE id = ?",
                (email.strip().lower(), user_id),
            )

    def set_password_hash(self, user_id: int, pwhash: str) -> None:
        with self._conn() as con:
            con.execute("UPDATE users SET pwhash = ? WHERE id = ?", (pwhash, user_id))

    def set_reset_token(self, user_id: int, token: str, expires_at: datetime) -> None:
        expires = expires_at.isoformat(timespec="seconds")
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?",
                (token, expires, user_id),
            )

    def get_by_reset_token(self, token: str) -> User | None:
        token = (token or "").strip()
        if not token:
            return None
        with self._conn() as con:
            row = con.execute(
                "SELECT id, login, email, email_verified, reset_expires, created_at "
                "FROM users WHERE reset_token = ? AND reset_token <> ''",
                (token,),
            ).fetchone()
        if not row:
            return None
        expires = row["reset_expires"]
        if not expires:
            return None
        try:
            if datetime.now(timezone.utc) > datetime.fromisoformat(expires):
                return None
        except Exception:
            return None
        user = self._row_to_user(row)
        user.is_admin = self.is_admin(user.id)
        return user

    def clear_reset_token(self, user_id: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token = '', reset_expires = '' WHERE id = ?",
                (user_id,),
            )

    def _ensure_admin_table(self) -> None:
        with self._conn() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS admins ("
                "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
                "module TEXT NOT NULL DEFAULT 'portal', "
                "PRIMARY KEY (user_id, module))"
            )

    def is_admin(self, user_id: int | None) -> bool:
        if not user_id:
            return False
        with self._conn() as con:
            row = con.execute(
                "SELECT 1 FROM admins WHERE user_id = ? AND module = 'portal'",
                (user_id,),
            ).fetchone()
        return bool(row)

    def list_admins(self) -> list[User]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT u.id, u.login, u.email, u.email_verified, u.created_at "
                "FROM admins a JOIN users u ON u.id = a.user_id "
                "WHERE a.module = 'portal' ORDER BY u.login"
            ).fetchall()
        users = [self._row_to_user(r) for r in rows]
        for user in users:
            user.is_admin = True
        return users

    def add_admin(self, user_id: int) -> None:
        self._ensure_admin_table()
        with self._conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO admins (user_id, module) VALUES (?, 'portal')",
                (user_id,),
            )

    def remove_admin(self, user_id: int) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM admins WHERE user_id = ? AND module = 'portal'",
                (user_id,),
            )
