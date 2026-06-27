"""Portal identity business logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from avalone_core.database import Service

from avalone_landing.core.models import User
from avalone_landing.core.user_repository import UserRepository


class UserService(Service):
    """User authentication and account management for the Avalone portal."""

    _RESET_TOKEN_TTL_HOURS = 1
    _MIN_PASSWORD_LENGTH = 6

    def __init__(self, repository: UserRepository | None = None) -> None:
        self._repo = repository or UserRepository()

    def authenticate(self, login: str, password: str) -> User | None:
        login = login.strip().lower()
        candidate = self._repo.get_by_login_or_email(login)
        if candidate and self._repo.verify_password(password, self._pwhash_for(candidate.login)):
            return self._repo.get_by_id(candidate.id)
        return None

    def _pwhash_for(self, login: str) -> str:
        with self._repo._conn() as con:
            row = con.execute(
                "SELECT pwhash FROM users WHERE login = ?", (login,)
            ).fetchone()
        if not row:
            return ""
        return row["pwhash"]

    def get_user(self, user_id: int) -> User | None:
        return self._repo.get_by_id(user_id)

    def create_user(self, login: str, password: str, email: str = "") -> int:
        if len(password) < self._MIN_PASSWORD_LENGTH:
            raise ValueError("password too short")
        return self._repo.create(login, password, email)

    def login_taken(self, login: str) -> bool:
        return self._repo.get_by_login_or_email(login) is not None

    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        if len(new_password) < self._MIN_PASSWORD_LENGTH:
            raise ValueError("password too short")
        user = self._repo.get_by_id(user_id)
        if not user:
            return False
        pwhash = self._pwhash_for(user.login)
        if not pwhash or not self._repo.verify_password(current_password, pwhash):
            return False
        self._repo.set_password_hash(user_id, self._repo.hash_password(new_password))
        return True

    def request_password_reset(self, login_or_email: str) -> tuple[User, str] | None:
        user = self._repo.get_by_login_or_email(login_or_email)
        if not user:
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=self._RESET_TOKEN_TTL_HOURS)
        self._repo.set_reset_token(user.id, token, expires)
        return user, token

    def get_user_by_reset_token(self, token: str) -> User | None:
        return self._repo.get_by_reset_token(token)

    def reset_password(self, token: str, new_password: str) -> User | None:
        if len(new_password) < self._MIN_PASSWORD_LENGTH:
            raise ValueError("password too short")
        user = self._repo.get_by_reset_token(token)
        if not user:
            return None
        self._repo.set_password_hash(user.id, self._repo.hash_password(new_password))
        self._repo.clear_reset_token(user.id)
        return self._repo.get_by_id(user.id)

    def is_admin(self, user_id: int | None) -> bool:
        return self._repo.is_admin(user_id)

    def list_users(self) -> list[User]:
        with self._repo._conn() as con:
            rows = con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users ORDER BY login"
            ).fetchall()
        users = []
        for row in rows:
            user = User(
                id=row["id"],
                login=row["login"],
                email=row["email"] or "",
                created_at=row["created_at"],
                email_verified=bool(row["email_verified"]),
            )
            user.is_admin = self._repo.is_admin(user.id)
            users.append(user)
        return users

    def list_admins(self) -> list[User]:
        return self._repo.list_admins()

    def ensure_admin(self, user_id: int) -> None:
        self._repo.add_admin(user_id)
