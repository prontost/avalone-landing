"""User data access for the Avalone portal."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository

from avalone_landing.core.models import User


class UserRepository(Repository):
    """SQL access for the portal `users`, `roles` and `user_roles` tables."""

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

    def _roles_for(self, user_id: int) -> list[str]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT r.name FROM roles r "
                "JOIN user_roles ur ON ur.role_id = r.id "
                "WHERE ur.user_id = ? ORDER BY r.name",
                (user_id,),
            ).fetchall()
        return [r["name"] for r in rows]

    def _permissions_for(self, user_id: int) -> set[str]:
        import json

        with self._conn() as con:
            rows = con.execute(
                "SELECT r.permissions FROM roles r "
                "JOIN user_roles ur ON ur.role_id = r.id "
                "WHERE ur.user_id = ?",
                (user_id,),
            ).fetchall()
        perms: set[str] = set()
        for row in rows:
            perms.update(json.loads(row["permissions"]))
        return perms

    def _row_to_user(self, row: sqlite3.Row) -> User:
        user = User(
            id=row["id"],
            login=row["login"],
            email=row["email"] or "",
            created_at=row["created_at"],
            name=row["name"] or "",
            email_verified=bool(row["email_verified"]),
            language=row["language"] or "auto",
        )
        user.roles = self._roles_for(user.id)
        user.permissions = sorted(self._permissions_for(user.id))
        user.is_admin = "admin:full" in user.permissions or "users:manage" in user.permissions
        return user

    def get_roles(self, user_id: int) -> list[str]:
        return self._roles_for(user_id)

    def get_permissions(self, user_id: int) -> list[str]:
        return sorted(self._permissions_for(user_id))

    def get_by_id(self, user_id: int) -> User | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT id, login, name, email, email_verified, language, referral_code, referred_by, created_at "
                "FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def get_by_login_or_email(self, value: str) -> User | None:
        value = value.strip().lower()
        with self._conn() as con:
            row = con.execute(
                "SELECT id, login, name, email, email_verified, language, referral_code, referred_by, created_at "
                "FROM users WHERE login = ? OR email = ?",
                (value, value),
            ).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def get_pwhash_by_login(self, login: str) -> str:
        with self._conn() as con:
            row = con.execute(
                "SELECT pwhash FROM users WHERE login = ?", (login.strip().lower(),)
            ).fetchone()
        return row["pwhash"] if row else ""

    def list_all(self) -> list[User]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, login, name, email, email_verified, language, referral_code, referred_by, created_at "
                "FROM users ORDER BY login"
            ).fetchall()
        return [self._row_to_user(row) for row in rows if row["id"]]

    def create(self, login: str, password: str, email: str = "") -> int:
        login = login.strip().lower()
        if not login or not password:
            raise ValueError("login and password are required")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO users (login, pwhash, email, referral_code, referred_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (login, self.hash_password(password), email.strip().lower(), None, None, now),
            )
            return cur.lastrowid or 0

    def update_email(self, user_id: int, email: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET email = ?, email_verified = 0 WHERE id = ?",
                (email.strip().lower(), user_id),
            )

    def update_name(self, user_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET name = ? WHERE id = ?",
                (name.strip(), user_id),
            )

    def set_verify_code(self, user_id: int, code: str, expires_at: datetime) -> None:
        expires = expires_at.isoformat(timespec="seconds")
        with self._conn() as con:
            con.execute(
                "UPDATE users SET verify_code = ?, verify_sent = ? WHERE id = ?",
                (code, expires, user_id),
            )

    def check_verify_code(self, user_id: int, code: str) -> bool:
        with self._conn() as con:
            row = con.execute(
                "SELECT verify_code, verify_sent FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row or not row["verify_code"]:
            return False
        if row["verify_code"] != code.strip():
            return False
        expires = row["verify_sent"]
        if not expires:
            return False
        try:
            if datetime.now(timezone.utc) > datetime.fromisoformat(expires):
                return False
        except Exception:
            return False
        return True

    def mark_email_verified(self, user_id: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET email_verified = 1, verify_code = '', verify_sent = '' WHERE id = ?",
                (user_id,),
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
                "SELECT id, login, name, email, email_verified, reset_expires, created_at "
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
        return self._row_to_user(row)

    def clear_reset_token(self, user_id: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token = '', reset_expires = '' WHERE id = ?",
                (user_id,),
            )
