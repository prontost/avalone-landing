"""Собственный двойной леджер в avalone.db (SQLite) — замена ERPNext-движка.

Цель переезда (Дэн, 2026-06-16): зависеть от ERPNext по минимуму, в итоге уйти
совсем. ERPNext делал для нас 3 вещи — план счетов, проводки (двойная запись),
балансы. Всё это здесь, на нашем SQLite, рядом с money_accounts/catalog_i18n.

Контракт намеренно повторяет сигнатуры `core/erpnext.py`, чтобы переключение шло
за единым фасадом с минимальными правками вызовов (см. шаг 3 переезда).

(Отдельный модуль от заброшенного core/ledger.py — тот на SQLAlchemy/Postgres и
Telegram-тенантах, мёртвый. Здесь — SQLite, single-user, в нашей avalone.db.)

Модель:
- money_led_accounts: name(PK, "Имя - DP"), account_name, root_type
  (Asset|Liability|Equity|Income|Expense), account_type, is_group, disabled.
- money_led_entries: проводка. docstatus 1=активна, 2=отменена.
- money_led_lines: строки. Инвариант sum(debit)==sum(credit) на проводку; CHECK строки.

ВАЖНО (требование Дэна): окончательное удаление здесь ТРИВИАЛЬНО — DELETE строк,
без «надгробий»-призраков, в отличие от append-only ERPNext.

This module is now a backward-compatible facade over :class:`LedgerService`.
All raw SQL lives in :mod:`ledger_repository`, and business logic lives in
:mod:`ledger_service`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from avalone_finance.core.ledger_service import LedgerError, LedgerService


ABBR = LedgerService.ABBR

_default_service = LedgerService()

# Backward-compatible module-level API. Signatures match the originals so that
# existing callers (web routes, tests, catalog seeding) keep working.
make_pk = _default_service.make_pk
group_parent = _default_service.group_parent
list_accounts = _default_service.list_accounts
create_account = _default_service.create_account
create_account_id = _default_service.create_account_id
upsert_account = _default_service.upsert_account
disable_account = _default_service.disable_account
enable_account = _default_service.enable_account
delete_account = _default_service.delete_account
post_journal_entry = _default_service.post_journal_entry
cancel_journal_entry = _default_service.cancel_journal_entry
restore_cancelled = _default_service.restore_cancelled
set_status = _default_service.set_status
delete_entry = _default_service.delete_entry
entry_accounts = _default_service.entry_accounts
entry_detail = _default_service.entry_detail
entries_of_account = _default_service.entries_of_account
entry_counts = _default_service.entry_counts
account_balance = _default_service.account_balance
recent_entries = _default_service.recent_entries
find_entry = _default_service.find_entry
assert_balanced = _default_service.assert_balanced


# keep private helpers available for any internal callers that used them
_tid = _default_service._tid
