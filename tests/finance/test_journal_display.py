"""Journal display: operation type, disabled-account labels, edit fields."""
import asyncio
from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    import avalone_finance.core.sqlledger as sl
    import avalone_finance.core.engine as engine
    import avalone_finance.core.global_settings as gs
    import avalone_finance.core.money as money
    import avalone_finance.core.catalog as catalog
    importlib.reload(tenant)
    importlib.reload(sl)
    importlib.reload(engine)
    importlib.reload(gs)
    importlib.reload(money)
    importlib.reload(catalog)
    tenant.set_current(1)

    from fastapi.testclient import TestClient
    from avalone_finance.web.app import finance_app as app

    c = TestClient(app)
    tenant.ensure_owner("owner", "ownerpass")
    return c


async def _seed_expense():
    from avalone_finance.core import engine, money
    cash = await engine.create_account("Cash", None, "Asset", "Cash")
    groc = await engine.create_account("Groceries", None, "Expense")
    money.register(cash, "cash", 0, "KRW")
    entry_id = await engine.post_journal_entry(
        date.today(), "bread", groc, cash, Decimal("30"))
    return cash, groc, entry_id


async def _seed_income():
    from avalone_finance.core import engine, money
    cash = await engine.create_account("Cash", None, "Asset", "Cash")
    sal = await engine.create_account("Salary", None, "Income")
    money.register(cash, "cash", 0, "KRW")
    entry_id = await engine.post_journal_entry(
        date.today(), "salary", cash, sal, Decimal("500"))
    return cash, sal, entry_id


async def _seed_transfer():
    from avalone_finance.core import engine, money
    card = await engine.create_account("Bank KB", None, "Asset", "Bank")
    cash = await engine.create_account("Cash", None, "Asset", "Cash")
    money.register(card, "bank", 0, "KRW")
    money.register(cash, "cash", 1, "KRW")
    entry_id = await engine.post_journal_entry(
        date.today(), "transfer", cash, card, Decimal("100"))
    return card, cash, entry_id


def test_journal_expense_op_and_labels(client):
    cash, groc, _ = asyncio.run(_seed_expense())
    r = client.get("/api/entries?limit=1")
    assert r.status_code == 200
    e = r.json()["entries"][0]
    assert e["op"] == "expense"
    assert e["to_name"] == groc
    assert e["to"] and " - DP" not in e["to"] and not e["to"].startswith("cat_")
    assert e["from_name"] == cash
    assert e["from"] and " - DP" not in e["from"]


def test_journal_income_op_and_labels(client):
    cash, sal, _ = asyncio.run(_seed_income())
    r = client.get("/api/entries?limit=1")
    assert r.status_code == 200
    e = r.json()["entries"][0]
    assert e["op"] == "income"
    assert e["to_name"] == cash
    assert e["from_name"] == sal


def test_journal_transfer_op_and_labels(client):
    card, cash, _ = asyncio.run(_seed_transfer())
    r = client.get("/api/entries?limit=1")
    assert r.status_code == 200
    e = r.json()["entries"][0]
    assert e["op"] == "transfer"
    assert e["to_name"] == cash
    assert e["from_name"] == card


def test_journal_disabled_category_shows_label_not_key(client):
    cash, groc, _ = asyncio.run(_seed_expense())
    from avalone_finance.core import engine
    asyncio.run(engine.disable_account(groc))
    r = client.get("/api/entries?limit=1")
    assert r.status_code == 200
    e = r.json()["entries"][0]
    assert e["to"] and " - DP" not in e["to"] and not e["to"].startswith("cat_")
