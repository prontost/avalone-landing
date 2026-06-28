"""Фасад движка книги: единая async-точка над леджером.

После переезда (2026-06-16) движок один — наш SQLite-леджер `core/sqlledger`
в единой БД Avalone. ERPNext удалён полностью. Фасад оставлен как тонкий async-слой
(вызовы в коде идут через `engine.*`), чтобы не переписывать ~50 мест и иметь
единую точку, если движок снова сменится.

Все функции async (для sqlledger — тонкая sync→async обёртка).
`engine.EngineError` — общий тип ошибки.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from avalone_finance.core.ledger_service import LedgerError, LedgerService


class EngineError(Exception):
    pass


_default_service = LedgerService()


# ----------------------------------------------------------------- счета
async def list_accounts(*, leaf_only: bool = True, include_disabled: bool = False) -> list[dict]:
    return _default_service.list_accounts(leaf_only=leaf_only, include_disabled=include_disabled)


async def create_account(account_name: str, parent_account, root_type: str,
                         account_type: str = "") -> str:
    return _default_service.create_account(account_name, parent_account, root_type, account_type)


async def group_parent(root_type: str):
    return _default_service.group_parent(root_type)


async def disable_account(name: str) -> None:
    _default_service.disable_account(name)


async def enable_account(name: str) -> None:
    _default_service.enable_account(name)


async def delete_account(name: str) -> None:
    try:
        _default_service.delete_account(name)
    except LedgerError as e:
        raise EngineError(str(e))


# ----------------------------------------------------------------- проводки
async def post_journal_entry(entry_date: date, remark: str, debit_account: str,
                             credit_account: str, amount: Decimal) -> str:
    try:
        return _default_service.post_journal_entry(
            entry_date, remark, debit_account, credit_account, amount
        )
    except LedgerError as e:
        raise EngineError(str(e))


async def cancel_journal_entry(name: str) -> None:
    _default_service.cancel_journal_entry(name)


async def restore_entry(name: str) -> str:
    """Вернуть отменённую проводку — обратимо напрямую (тот же id)."""
    _default_service.restore_cancelled(name)
    return name


async def delete_entry(name: str) -> None:
    _default_service.delete_entry(name)


async def entry_accounts(name: str):
    return _default_service.entry_accounts(name)


async def entry_detail(name: str):
    return _default_service.entry_detail(name)


async def entries_of_account(account: str, docstatus: tuple = (1,)) -> list[str]:
    return _default_service.entries_of_account(account, docstatus=docstatus)


async def entry_counts(account_names: list[str]) -> dict[str, int]:
    return _default_service.entry_counts(account_names)


async def account_balance(account: str, on_date: date | None = None) -> Decimal:
    return _default_service.account_balance(account, on_date)


async def recent_entries(limit: int = 10, *, extra_filters: list | None = None,
                         order_by: str = "posting_date desc, name desc",
                         docstatus: tuple = (1,)) -> list[dict]:
    return _default_service.recent_entries(
        limit=limit, extra_filters=extra_filters, order_by=order_by, docstatus=docstatus
    )


async def find_entry(keywords: str, limit: int | None = None):
    return _default_service.find_entry(keywords, limit)
