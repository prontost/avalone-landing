"""Business logic for per-entry metadata and slept entries.

Service resolves the current tenant from the request context and delegates SQL
to `EntryMetaRepository`.
"""

from __future__ import annotations

from datetime import datetime

from avalone_core.database import Service
from avalone_finance.core.entry_meta_repository import EntryMetaRepository
from avalone_finance.core.tenant import TenantService


class EntryMetaService(Service):
    """Manage occurred_at timestamps and slept entry snapshots."""

    def __init__(
        self,
        repository: EntryMetaRepository | None = None,
        tenant_service: TenantService | None = None,
    ) -> None:
        self._repo = repository or EntryMetaRepository()
        self._tenant = tenant_service or TenantService()

    def _tid(self) -> int:
        return self._tenant.require_current()

    def set_occurred(self, voucher: str, occurred_at: str) -> None:
        self._repo.set_occurred(self._tid(), voucher, occurred_at)

    def occurred_map(self, vouchers: list[str]) -> dict[str, str]:
        return self._repo.occurred_map(self._tid(), vouchers)

    def sleep_record(self, account: str, snap: dict, occurred_at: str | None) -> None:
        self._repo.sleep_record(self._tid(), account, snap, occurred_at)

    def sleeping_for(self, account: str) -> list[dict]:
        return self._repo.sleeping_for(self._tid(), account)

    def clear_sleeping(self, account: str) -> None:
        self._repo.clear_sleeping(self._tid(), account)

    def forget(self, voucher: str) -> None:
        self._repo.forget(self._tid(), voucher)

    @staticmethod
    def parse_occurred(value: str | None) -> datetime | None:
        """Parse an ISO-datetime from the form; None if empty/invalid.

        Accepts `datetime-local` (YYYY-MM-DDTHH:MM[:SS]) and full ISO formats.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
