"""Тесты собственного SQLite-леджера (шаг 1 переезда с ERPNext).

Главное — инвариант двойной записи и корректность балансов/отмены/удаления.
Используем изолированную temp-БД через monkeypatch DB_PATH.
"""
from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def led(tmp_path, monkeypatch):
    # своя БД на тест — не трогаем рабочую counta.db
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    importlib.reload(tenant)
    tenant.set_current(1)
    import avalone_finance.core.sqlledger as sl
    importlib.reload(sl)
    # счета: денежный (актив) + категория (расход) + доход
    sl.create_account("Cash", None, "Asset", "Cash")
    sl.create_account("Groceries", None, "Expense")
    sl.create_account("Salary", None, "Income")
    return sl


def test_post_is_balanced(led):
    cash = led.make_pk("Cash"); groc = led.make_pk("Groceries")
    led.post_journal_entry(date(2026, 6, 1), "хлеб", groc, cash, Decimal("30"))
    led.assert_balanced()
    # расход с Cash -> баланс Cash = -30 (потратил), Groceries = +30
    assert led.account_balance(cash) == Decimal("-30")
    assert led.account_balance(groc) == Decimal("30")


def test_income_and_sign(led):
    cash = led.make_pk("Cash"); sal = led.make_pk("Salary")
    led.post_journal_entry(date(2026, 6, 1), "зп", cash, sal, Decimal("1000"))
    assert led.account_balance(cash) == Decimal("1000")   # деньги пришли (+)


def test_cancel_removes_from_balance_and_reversible(led):
    cash = led.make_pk("Cash"); sal = led.make_pk("Salary")
    e = led.post_journal_entry(date(2026, 6, 1), "зп", cash, sal, Decimal("500"))
    assert led.account_balance(cash) == Decimal("500")
    led.cancel_journal_entry(e)
    assert led.account_balance(cash) == Decimal("0")      # отмена убрала из баланса
    led.restore_cancelled(e)
    assert led.account_balance(cash) == Decimal("500")    # отмена ОБРАТИМА напрямую


def test_hard_delete_no_ghost(led):
    cash = led.make_pk("Cash"); groc = led.make_pk("Groceries")
    e = led.post_journal_entry(date(2026, 6, 1), "x", groc, cash, Decimal("10"))
    led.cancel_journal_entry(e)
    led.delete_entry(e)
    # ни в активных, ни в отменённых — призрака нет
    assert led.entries_of_account(cash, docstatus=(1, 2)) == []
    led.assert_balanced()


def test_negative_amount_rejected(led):
    cash = led.make_pk("Cash"); groc = led.make_pk("Groceries")
    with pytest.raises(led.LedgerError):
        led.post_journal_entry(date(2026, 6, 1), "x", groc, cash, Decimal("-5"))


def test_account_delete_blocked_while_used(led):
    cash = led.make_pk("Cash"); groc = led.make_pk("Groceries")
    e = led.post_journal_entry(date(2026, 6, 1), "x", groc, cash, Decimal("10"))
    with pytest.raises(led.LedgerError):
        led.delete_account(cash)
    led.delete_entry(e)
    led.delete_account(cash)   # после удаления проводки — счёт удаляется
    assert led.make_pk("Cash") not in {a["name"] for a in led.list_accounts(include_disabled=True)}
