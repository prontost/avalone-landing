"""Business logic for instance-wide global settings.

Only instance admins are allowed to change these settings.
"""

from __future__ import annotations

from typing import Any

from avalone_core.database import Service
from avalone_finance.core.global_settings_repository import GlobalSettingsRepository
from avalone_finance.core.tenant import TenantService


class GlobalSettingsService(Service):
    """Global settings service: reads are public, writes require admin."""

    def __init__(
        self,
        repository: GlobalSettingsRepository | None = None,
        tenant_service: TenantService | None = None,
    ) -> None:
        self._repo = repository or GlobalSettingsRepository()
        self._tenant = tenant_service or TenantService()

    def get(self, key: str) -> str | None:
        return self._repo.get(key)

    def set(self, key: str, value: str) -> None:
        """Only instance admins are allowed to change global settings."""
        if not self._tenant.is_admin(self._tenant.current()):
            raise PermissionError("only admins can change global settings")
        self._repo.set(key, value)

    def get_all(self) -> dict:
        return self._repo.get_all()

    def get_runtime(self) -> dict[str, Any]:
        """Runtime admin-facing settings merged from DB and env defaults."""
        from avalone_finance.core import money
        from avalone_finance.core.config import settings

        all_ = self.get_all()
        mode = (all_.get("registration_mode") or "").strip().lower()
        if mode not in ("open", "invite", "closed"):
            mode = settings().registration_mode
        return {
            "registration_mode": mode,
            "registration_invite_code": all_.get(
                "registration_invite_code", settings().registration_invite_code
            ),
            "strict_password_policy": str(
                all_.get("strict_password_policy", "")
            ).strip().lower() in ("1", "true", "yes", "on"),
            "default_currency": all_.get("default_currency") or money.DEFAULT_CURRENCY,
            "web_base_url": all_.get("web_base_url") or settings().web_base_url,
        }
