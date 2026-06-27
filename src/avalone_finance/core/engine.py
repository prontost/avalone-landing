"""Фасад движка книги: единая async-точка над леджером.

После переезда (2026-06-16) движок один — наш SQLite-леджер `core/sqlledger`
в counta.db. ERPNext удалён полностью. Фасад оставлен как тонкий async-слой
(вызовы в коде идут через `engine.*`), чтобы не переписывать ~50 мест и иметь
единую точку, если движок снова сменится.

Все функции async (для sqlledger — тонкая sync→async обёртка).
`engine.EngineError` — общий тип ошибки.
"""

from datetime import date
from decimal import Decimal

from avalone_core import glossary_db as glossary
from avalone_finance.core import constants, money, sqlledger


class EngineError(Exception):
    pass


# ----------------------------------------------------------------- счета
async def list_accounts(*, leaf_only: bool = True, include_disabled: bool = False) -> list[dict]:
    return sqlledger.list_accounts(leaf_only=leaf_only, include_disabled=include_disabled)


async def create_account(account_name: str, parent_account, root_type: str,
                         account_type: str = "") -> str:
    return sqlledger.create_account(account_name, parent_account, root_type, account_type)


async def group_parent(root_type: str):
    return sqlledger.group_parent(root_type)


async def disable_account(name: str) -> None:
    sqlledger.disable_account(name)


async def enable_account(name: str) -> None:
    sqlledger.enable_account(name)


async def delete_account(name: str) -> None:
    try:
        sqlledger.delete_account(name)
    except sqlledger.LedgerError as e:
        raise EngineError(str(e))


# ----------------------------------------------------------------- проводки
async def post_journal_entry(entry_date: date, remark: str, debit_account: str,
                             credit_account: str, amount: Decimal) -> str:
    # Перевод возможен только между счетами в одной валюте.
    if money.is_money(debit_account) and money.is_money(credit_account):
        if money.account_currency(debit_account) != money.account_currency(credit_account):
            raise EngineError(glossary.t("error_transfer_currency_mismatch", lang="ru"))
    try:
        return sqlledger.post_journal_entry(entry_date, remark, debit_account, credit_account, amount)
    except sqlledger.LedgerError as e:
        raise EngineError(str(e))


async def cancel_journal_entry(name: str) -> None:
    sqlledger.cancel_journal_entry(name)


async def restore_entry(name: str) -> str:
    """Вернуть отменённую проводку — обратимо напрямую (тот же id)."""
    sqlledger.restore_cancelled(name)
    return name


async def delete_entry(name: str) -> None:
    sqlledger.delete_entry(name)


async def entry_accounts(name: str):
    return sqlledger.entry_accounts(name)


async def entry_detail(name: str):
    return sqlledger.entry_detail(name)


async def entries_of_account(account: str, docstatus: tuple = (1,)) -> list[str]:
    return sqlledger.entries_of_account(account, docstatus=docstatus)


async def entry_counts(account_names: list[str]) -> dict[str, int]:
    return sqlledger.entry_counts(account_names)


async def account_balance(account: str, on_date: date | None = None) -> Decimal:
    return sqlledger.account_balance(account, on_date)


async def recent_entries(limit: int = 10, *, extra_filters: list | None = None,
                         order_by: str = "posting_date desc, name desc",
                         docstatus: tuple = (1,)) -> list[dict]:
    return sqlledger.recent_entries(limit=limit, extra_filters=extra_filters,
                                    order_by=order_by, docstatus=docstatus)


async def find_entry(keywords: str, limit: int | None = None):
    if limit is None:
        limit = constants.get("find_entry_limit")
    return sqlledger.find_entry(keywords, limit)
