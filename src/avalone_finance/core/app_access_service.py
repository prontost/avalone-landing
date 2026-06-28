"""Business logic for per-user app access permissions.

The app registry (`KNOWN_APPS`) lives in code. Public apps are accessible by
default; explicit overrides are stored in `money_user_apps`.
"""

from __future__ import annotations

from avalone_core.database import Service
from avalone_finance.core.app_access_repository import AppAccessRepository

# Реестр приложений платформы. id — технический ключ, используется в URL/API.
KNOWN_APPS: dict[str, dict] = {
    "money": {
        "id": "money",
        "name": "Финансы",
        "icon": "🪙",
        "public": True,
        "url": "https://avalone.online/finance",
    },
    "work": {
        "id": "work",
        "name": "Работа",
        "icon": "🚐",
        "public": True,
        "url": "https://avalone.online/work",
    },
}


class AppAccessService(Service):
    """Manage which platform apps a user can see/use."""

    def __init__(self, repository: AppAccessRepository | None = None) -> None:
        self._repo = repository or AppAccessRepository()

    def registry(self) -> list[dict]:
        """Public registry of all platform apps (for UI)."""
        return [dict(meta) for meta in KNOWN_APPS.values()]

    def list_for_user(self, user_id: int) -> list[str]:
        """List app_ids accessible to the user (for the app switcher)."""
        explicit = self._repo.rows_for(user_id)
        return [
            app_id
            for app_id, meta in KNOWN_APPS.items()
            if explicit.get(app_id, meta.get("public", False))
        ]

    def is_accessible(self, user_id: int, app_id: str) -> bool:
        meta = KNOWN_APPS.get(app_id)
        if not meta:
            return False
        explicit = self._repo.rows_for(user_id)
        return explicit.get(app_id, meta.get("public", False))

    def list_for_admin(self, user_id: int) -> list[dict]:
        """Detailed access state for the admin panel (all known apps)."""
        explicit = self._repo.rows_for(user_id)
        return [
            {
                "id": app_id,
                "name": meta["name"],
                "icon": meta.get("icon", ""),
                "enabled": explicit.get(app_id, meta.get("public", False)),
            }
            for app_id, meta in KNOWN_APPS.items()
        ]

    def set_access(self, user_id: int, app_id: str, enabled: bool) -> None:
        """Enable or disable access to an app for a user."""
        if app_id not in KNOWN_APPS:
            raise ValueError(f"unknown app: {app_id}")
        self._repo.set_access(user_id, app_id, enabled)

    def grant_default(self, user_id: int) -> None:
        """Grant access to all public apps on registration."""
        for app_id, meta in KNOWN_APPS.items():
            if meta.get("public"):
                self.set_access(user_id, app_id, True)

    def delete_for_user(self, user_id: int) -> None:
        """Delete all access records for a user."""
        self._repo.delete_for_user(user_id)
