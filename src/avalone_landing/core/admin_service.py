"""Admin service for the Avalone portal platform administration panel."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from avalone_core.database import Service

from avalone_landing.config import settings
from avalone_landing.core.admin_repository import AdminRepository
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_repository import UserRepository


@dataclass
class AdminUser(User):
    """User enriched with admin role flags and module data counts."""

    is_platform_admin: bool = False
    is_money_admin: bool = False
    is_work_admin: bool = False
    module_counts: dict[str, int] = field(default_factory=dict)


class AdminService(Service):
    """Business logic for platform admin operations."""

    _RESET_TOKEN_TTL_HOURS = 1
    _MIN_PASSWORD_LENGTH = 6

    _SETTING_KEYS = {
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_use_tls",
        "mail_from",
        "mail_from_name",
        "push_vapid_public",
        "push_vapid_private",
    }

    def __init__(
        self,
        repository: AdminRepository | None = None,
        user_repository: UserRepository | None = None,
        mail_service: MailService | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self._repo = repository or AdminRepository()
        self._user_repo = user_repository or UserRepository()
        self._mail = mail_service or MailService()
        self._auth = auth_service

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def list_users(self) -> list[AdminUser]:
        rows = self._repo.list_users()
        users: list[AdminUser] = []
        for row in rows:
            user = self._admin_user_from_row(row)
            user.module_counts = self._repo.module_counts(user.id)
            users.append(user)
        return users

    def get_user(self, user_id: int) -> AdminUser | None:
        row = self._repo.get_user(user_id)
        if not row:
            return None
        user = self._admin_user_from_row(row)
        user.module_counts = self._repo.module_counts(user.id)
        return user

    def _admin_user_from_row(self, row: Any) -> AdminUser:
        roles = self._repo.get_roles(row["id"])
        user = AdminUser(
            id=row["id"],
            login=row["login"],
            email=row["email"] or "",
            created_at=row["created_at"],
            email_verified=bool(row["email_verified"]),
            is_admin="portal" in roles,
            roles=roles,
            is_platform_admin="portal" in roles,
            is_money_admin="money" in roles,
            is_work_admin="work" in roles,
        )
        return user

    def update_user(self, user_id: int, email: str | None = None, roles: list[str] | None = None) -> AdminUser | None:
        if not self._repo.user_exists(user_id):
            return None
        if email is not None:
            self._repo.update_email(user_id, email)
        if roles is not None:
            self._repo.set_roles(user_id, roles)
        return self.get_user(user_id)

    # ------------------------------------------------------------------
    # Password
    # ------------------------------------------------------------------

    def reset_password_link(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=self._RESET_TOKEN_TTL_HOURS)
        self._repo.set_reset_token(user_id, token, expires.isoformat(timespec="seconds"))
        return f"{settings().web_base_url}/reset-password?token={token}"

    def set_temporary_password(self, user_id: int, password: str) -> None:
        if len(password) < self._MIN_PASSWORD_LENGTH:
            raise ValueError("password too short")
        self._repo.set_password_hash(user_id, self._user_repo.hash_password(password))
        self._repo.clear_reset_token(user_id)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def wipe_user_data(self, user_id: int) -> dict[str, int]:
        return self._repo.wipe_user_data(user_id)

    def export_user_data(self, user_id: int) -> dict[str, Any]:
        user_row = self._repo.get_user(user_id)
        if not user_row:
            return {"user": None, "roles": [], "modules": {"money": {}, "work": {}}}
        return {
            "user": dict(user_row),
            "roles": self._repo.get_roles(user_id),
            "modules": self._repo.export_user_data(user_id),
        }

    def transfer_user_data(self, from_user_id: int, to_user_id: int) -> dict[str, int]:
        if not self._repo.user_exists(from_user_id):
            raise ValueError("source user not found")
        if not self._repo.user_exists(to_user_id):
            raise ValueError("target user not found")
        return self._repo.transfer_user_data(from_user_id, to_user_id)

    def copy_user_data(self, from_user_id: int, to_user_id: int, tables: list[str]) -> dict[str, int]:
        if not self._repo.user_exists(from_user_id):
            raise ValueError("source user not found")
        if not self._repo.user_exists(to_user_id):
            raise ValueError("target user not found")
        return self._repo.copy_tables(from_user_id, to_user_id, tables)

    # ------------------------------------------------------------------
    # Server settings
    # ------------------------------------------------------------------

    def list_server_settings(self) -> dict[str, Any]:
        raw = self._repo.list_server_settings()
        cfg = settings()
        defaults = {
            "smtp_host": cfg.smtp_host,
            "smtp_port": str(cfg.smtp_port),
            "smtp_user": cfg.smtp_user,
            "smtp_password": cfg.smtp_password,
            "smtp_use_tls": "true" if cfg.smtp_use_tls else "false",
            "mail_from": cfg.mail_from,
            "mail_from_name": cfg.mail_from_name,
            "push_vapid_public": "",
            "push_vapid_private": "",
        }
        settings_out: dict[str, Any] = {}
        for key in self._SETTING_KEYS:
            value = raw.get(key, defaults.get(key, ""))
            if key == "smtp_port":
                settings_out[key] = int(value) if value else 587
            elif key == "smtp_use_tls":
                settings_out[key] = str(value).lower() not in ("", "0", "false", "no", "off")
            else:
                settings_out[key] = value
        return settings_out

    def update_server_settings(self, settings: dict[str, Any]) -> None:
        raw: dict[str, str] = {}
        for key, value in settings.items():
            if key not in self._SETTING_KEYS:
                continue
            if isinstance(value, bool):
                raw[key] = "true" if value else "false"
            else:
                raw[key] = str(value)
        self._repo.set_server_settings(raw)

    def send_test_email(self, to: str) -> None:
        cfg = self.list_server_settings()
        self._mail.send_email_with_config(
            to=to,
            subject="Avalone test email",
            body="This is a test email from the Avalone admin panel.",
            cfg=cfg,
        )
