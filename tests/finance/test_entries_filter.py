"""Journal filters: op_type, income source, and existing filters via TestClient."""
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
    importlib.reload(tenant)
    importlib.reload(sl)
    importlib.reload(engine)
    importlib.reload(gs)
    tenant.set_current(1)

    from fastapi.testclient import TestClient
    from avalone_finance.web.app import finance_app as app

    c = TestClient(app)
    # seed tenant; auth_gate is monkey-patched in conftest to trust tenant.current()
    tenant.ensure_owner("owner", "ownerpass")
    return c


@pytest.fixture
def seed_entries(client):
    from avalone_finance.core import tenant, engine
    tenant.set_current(tenant.authenticate("owner", "ownerpass"))

    async def _seed():
        cash = await engine.create_account("Cash", None, "Asset", "Cash")
        card = await engine.create_account("Card", None, "Asset", "Bank")
        groc = await engine.create_account("Groceries", None, "Expense")
        sal = await engine.create_account("Salary", None, "Income")
        taxi = await engine.create_account("Taxi", None, "Expense")
        await engine.post_journal_entry(date(2026, 6, 1), "bread", groc, cash, Decimal("30"))
        await engine.post_journal_entry(date(2026, 6, 2), "salary", cash, sal, Decimal("500"))
        await engine.post_journal_entry(date(2026, 6, 3), "transfer", card, cash, Decimal("100"))
        await engine.post_journal_entry(date(2026, 6, 4), "taxi", taxi, cash, Decimal("20"))
        return {"cash": cash, "card": card, "groc": groc, "sal": sal, "taxi": taxi}

    return asyncio.run(_seed())


def test_filter_op_type_expense(client, seed_entries):
    r = client.get("/api/entries?op_type=expense")
    assert r.status_code == 200
    data = r.json()
    assert all("bread" in (e["remark"] or "") or "taxi" in (e["remark"] or "") for e in data["entries"])
    assert len(data["entries"]) == 2


def test_filter_op_type_income(client, seed_entries):
    r = client.get("/api/entries?op_type=income")
    assert r.status_code == 200
    data = r.json()
    assert all("salary" in (e["remark"] or "") for e in data["entries"])
    assert len(data["entries"]) == 1


def test_filter_op_type_transfer(client, seed_entries):
    r = client.get("/api/entries?op_type=transfer")
    assert r.status_code == 200
    data = r.json()
    assert all("transfer" in (e["remark"] or "") for e in data["entries"])
    assert len(data["entries"]) == 1


def test_filter_income_source(client, seed_entries):
    sal = seed_entries["sal"]
    r = client.get(f"/api/entries?income={sal}")
    assert r.status_code == 200
    data = r.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["remark"] == "salary"


def test_filter_category_and_income_combo(client, seed_entries):
    groc = seed_entries["groc"]
    r = client.get(f"/api/entries?category={groc}&op_type=expense")
    assert r.status_code == 200
    data = r.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["remark"] == "bread"
