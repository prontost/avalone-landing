"""Фасад движка: engine.* проксирует в sqlledger (единственный движок после
переезда с ERPNext). Проверяем сквозной путь через фасад."""
from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def eng(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    importlib.reload(tenant)
    tenant.set_current(1)
    import avalone_finance.core.sqlledger as sl
    importlib.reload(sl)
    import avalone_finance.core.engine as engine
    importlib.reload(engine)
    return engine


async def test_facade_post_and_balance(eng):
    cash = await eng.create_account("Cash", None, "Asset", "Cash")
    groc = await eng.create_account("Groceries", None, "Expense")
    assert len(await eng.list_accounts()) == 2
    await eng.post_journal_entry(date(2026, 6, 1), "хлеб", groc, cash, Decimal("30"))
    assert await eng.account_balance(cash) == Decimal("-30")


async def test_facade_cancel_restore_reversible(eng):
    cash = await eng.create_account("Cash", None, "Asset", "Cash")
    sal = await eng.create_account("Salary", None, "Income")
    e = await eng.post_journal_entry(date(2026, 6, 1), "зп", cash, sal, Decimal("500"))
    await eng.cancel_journal_entry(e)
    assert await eng.account_balance(cash) == Decimal("0")
    new = await eng.restore_entry(e)
    assert new == e                                  # тот же id (не пересоздание)
    assert await eng.account_balance(cash) == Decimal("500")


async def test_facade_hard_delete_no_ghost(eng):
    cash = await eng.create_account("Cash", None, "Asset", "Cash")
    groc = await eng.create_account("Groceries", None, "Expense")
    e = await eng.post_journal_entry(date(2026, 6, 1), "x", groc, cash, Decimal("10"))
    await eng.cancel_journal_entry(e)
    await eng.delete_entry(e)
    assert await eng.entries_of_account(cash, docstatus=(1, 2)) == []
