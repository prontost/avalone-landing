"""Локальные метаданные проводок, которых нет в схеме ERPNext Journal Entry.

ERPNext хранит `posting_date` (дата возникновения транзакции — управляется
пользователем) и `creation` (таймстамп создания записи — авто). Но у Journal
Entry нет поля ВРЕМЕНИ возникновения. Дэн хочет указывать дату И время, когда
tранзакция реально произошла, отдельно от момента внесения записи.

Поэтому время возникновения (полный ISO-datetime) держим здесь под ключом
`occurred_at` в таблице `money_entry_meta` единой БД. Дата всё равно дублируется
в posting_date, чтобы балансы/отчёты/фильтры работали нативно; здесь — точное
время.

Backward-compatible facade: module-level functions delegate to the default
EntryMetaService instance.
"""

from avalone_finance.core.entry_meta_repository import EntryMetaRepository
from avalone_finance.core.entry_meta_service import EntryMetaService

# --- backward-compatible module-level API ---
_default_service = EntryMetaService()

set_occurred = _default_service.set_occurred
occurred_map = _default_service.occurred_map
sleep_record = _default_service.sleep_record
sleeping_for = _default_service.sleeping_for
clear_sleeping = _default_service.clear_sleeping
forget = _default_service.forget
parse_occurred = EntryMetaService.parse_occurred

__all__ = [
    "EntryMetaRepository",
    "EntryMetaService",
    "set_occurred",
    "occurred_map",
    "sleep_record",
    "sleeping_for",
    "clear_sleeping",
    "forget",
    "parse_occurred",
]
