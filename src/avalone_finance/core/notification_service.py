"""Business logic for the per-user notification log.

Thin service over `NotificationRepository`; tenant_id is passed explicitly
because callers already know it.
"""

from __future__ import annotations

from avalone_core.database import Service
from avalone_finance.core.notification_repository import NotificationRepository


class NotificationService(Service):
    """Manage the notification log for a tenant/app."""

    def __init__(self, repository: NotificationRepository | None = None) -> None:
        self._repo = repository or NotificationRepository()

    def add(
        self, tenant_id: int, app: str, title: str, body: str = "", kind: str = "info"
    ) -> int:
        return self._repo.add(tenant_id, app, title, body, kind)

    def list_(
        self,
        tenant_id: int,
        app: str,
        filter: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._repo.list_(tenant_id, app, filter, limit, offset)

    def mark_read(self, ids: list[int], tenant_id: int) -> int:
        return self._repo.mark_read(ids, tenant_id)

    def mark_dismissed(self, ids: list[int], tenant_id: int) -> int:
        return self._repo.mark_dismissed(ids, tenant_id)

    def count_unread(self, tenant_id: int, app: str) -> int:
        return self._repo.count_unread(tenant_id, app)
