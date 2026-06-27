"""Portal identity business logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from avalone_core.database import Service
from avalone_core.referral_service import ReferralService

from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.core.user_repository import UserRepository


class UserService(Service):
    """User authentication and account management for the Avalone portal."""

    _RESET_TOKEN_TTL_HOURS = 1
    _MIN_PASSWORD_LENGTH = 6

    def __init__(self, repository: UserRepository | None = None) -> None:
        self._repo = repository or UserRepository()
        self._role_service = RoleService()

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

    def create_user(
        self, login: str, password: str, email: str = "", referral_code: str | None = None
    ) -> int:
        if len(password) < self._MIN_PASSWORD_LENGTH:
            raise ValueError("password too short")
        user_id = self._repo.create(login, password, email)
        if referral_code:
            ReferralService(user_repo=self._repo).apply_referral(
                user_id, referral_code, None
            )
        return user_id

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

    def get_roles(self, user_id: int) -> list[str]:
        return self._repo.get_roles(user_id)

    def has_permission(self, user_id: int | None, permission: str) -> bool:
        return self._role_service.has_permission(user_id, permission)

    def set_roles(self, user_id: int, role_names: list[str]) -> None:
        self._role_service.assign_roles(user_id, role_names)

    def list_users(self) -> list[User]:
        with self._repo._conn() as con:
            rows = con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users ORDER BY login"
            ).fetchall()
        return [self._repo.get_by_id(row["id"]) for row in rows if row["id"]]
