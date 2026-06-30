"""Smoke tests for endpoints that regressed during the api.py refactor."""
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
    import avalone_finance.core.ledger_repository as ledger_repo
    import avalone_finance.core.ledger_service as ledger_svc
    importlib.reload(tenant)
    importlib.reload(ledger_repo)
    importlib.reload(ledger_svc)
    importlib.reload(sl)
    importlib.reload(engine)
    importlib.reload(gs)
    tenant.set_current(1)

    from fastapi.testclient import TestClient
    from avalone_finance.web.app import finance_app as app

    c = TestClient(app)
    tenant.ensure_owner("owner", "ownerpass")
    tenant.add_admin(tenant.OWNER_TENANT_ID)
    tenant.set_current(tenant.OWNER_TENANT_ID)
    from avalone_finance.core import catalog
    asyncio.run(catalog.ensure_user_catalog())
    return c


@pytest.fixture
def seed_entries(client, monkeypatch):
    from avalone_finance.core import tenant, engine
    tenant.set_current(tenant.authenticate("owner", "ownerpass"))

    async def _seed():
        cash = await engine.create_account("Cash", None, "Asset", "Cash")
        card = await engine.create_account("Card", None, "Asset", "Bank")
        groc = await engine.create_account("Groceries", None, "Expense")
        other = await engine.create_account("Other", None, "Expense")
        sal = await engine.create_account("Salary", None, "Income")
        await engine.post_journal_entry(date(2026, 6, 1), "bread", groc, cash, Decimal("30"))
        await engine.post_journal_entry(date(2026, 6, 2), "salary", cash, sal, Decimal("500"))
        await engine.post_journal_entry(date(2026, 6, 3), "transfer", card, cash, Decimal("100"))
        await engine.post_journal_entry(date(2026, 6, 4), "taxi", other, cash, Decimal("20"))
        return cash, card, groc, other, sal

    return asyncio.run(_seed())


def test_report_endpoint(client, seed_entries):
    # Use an explicit custom date range so the test is stable across month boundaries.
    r = client.get("/api/report?period=custom&lang=ru&date_from=2026-06-01&date_to=2026-06-30")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["period"] == "custom"
    assert "groups" in data
    assert isinstance(data["groups"], list)
    # в тестовых данных есть расходы и доход
    assert any(g["expense"] > 0 for g in data["groups"])
    assert any(g["income"] > 0 for g in data["groups"])


def test_analytics_endpoints(client, seed_entries):
    # Use an explicit date range so the test is stable across month boundaries.
    r = client.get("/api/analytics/summary?period=last90&lang=ru")
    assert r.status_code == 200, r.text
    assert "groups" in r.json()

    r = client.get("/api/analytics/tip?period=last90&lang=ru")
    assert r.status_code == 200, r.text
    assert "title" in r.json()

    r = client.get("/api/analytics/tips?lang=ru")
    assert r.status_code == 200, r.text
    assert "tips" in r.json()

    r = client.get("/api/analytics/trend?period=last90&group_by=day&lang=ru")
    assert r.status_code == 200, r.text
    assert "series" in r.json()

    r = client.get("/api/analytics/compare?period=last90&lang=ru")
    assert r.status_code == 200, r.text
    assert "comparisons" in r.json()


def test_analytics_summary_includes_debts(client, seed_entries):
    """Трата из счёта-займа (Liability) создаёт отрицательный баланс — он должен
    попасть в debts в аналитике."""
    from avalone_finance.core import tenant, engine
    tenant.set_current(tenant.authenticate("owner", "ownerpass"))

    async def _make_debt():
        other = "Other"
        loan = await engine.create_account("Loan", None, "Liability", "Loan")
        # расход за счёт займа: debit Expense, credit Liability → баланс Loan = −200
        await engine.post_journal_entry(
            date(2026, 6, 5), "debt spend", other, loan, Decimal("200"))
    asyncio.run(_make_debt())

    r = client.get("/api/analytics/summary?period=last90&lang=ru")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "debts" in data
    assert any(d["debts"] > 0 for d in data["debts"]), data["debts"]
    assert all("net" in d for d in data["debts"])


def test_edit_endpoints(client, seed_entries):
    r = client.get("/api/edit/categories?lang=ru")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and len(data["items"]) >= 3

    r = client.get("/api/edit/incomes?lang=ru")
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_create_category_and_income(client, seed_entries):
    r = client.post("/api/category", json={"name": "Моя тестовая", "lang": "ru"})
    assert r.status_code == 200, r.text
    assert "name" in r.json()

    r = client.post("/api/income", json={"name": "Мой доход", "lang": "ru"})
    assert r.status_code == 200, r.text
    assert "name" in r.json()


def test_entries_filter_uncategorized(client, seed_entries):
    """only=uncategorized использует _is_misc — проверяем, что не 500."""
    r = client.get("/api/entries?only=uncategorized&lang=ru")
    assert r.status_code == 200, r.text


def test_account_disable_money_account(client, seed_entries):
    """Отключение денежного счёта использует _is_money_account."""
    r = client.post("/api/account/Cash/disable")
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_verify_code_uses_client_ip(client, monkeypatch):
    """/send-verify-code использует _client_ip — проверяем, что не 500."""
    from avalone_finance.core import tenant
    from avalone_finance.core.notify_service import NotifyService
    tenant.set_current(tenant.authenticate("owner", "ownerpass"))
    tenant.set_email(tenant.current(), "test@example.com")
    monkeypatch.setattr(NotifyService, "send_email", lambda *a, **kw: True)
    r = client.post("/api/send-verify-code")
    assert r.status_code == 200, r.text
    assert r.json().get("sent") is True


def test_admin_settings(client):
    r = client.get("/api/admin/settings")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "registration_mode" in data
    assert "registration_invite_code" in data
    assert isinstance(data["strict_password_policy"], bool)


def test_admin_settings_update(client):
    r = client.post("/api/admin/settings", json={"strict_password_policy": True})
    assert r.status_code == 200, r.text
    assert r.json()["strict_password_policy"] is True
    r = client.post("/api/admin/settings", json={"strict_password_policy": False})
    assert r.status_code == 200, r.text
    assert r.json()["strict_password_policy"] is False


def test_admin_users(client):
    r = client.get("/api/admin/users")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "users" in data
    assert any(u["login"] == "owner" for u in data["users"])


def test_admin_config(client):
    r = client.get("/api/admin/config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "runtime" in data
    assert "static" in data
    assert "env" in data
    assert "options" in data


def test_admin_stats_and_health(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "users" in data and "entries" in data and "currencies" in data

    r = client.get("/api/admin/health")
    assert r.status_code == 200, r.text
    assert r.json()["db_ok"] is True


def test_admin_constants(client):
    r = client.get("/api/admin/constants")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "constants" in data and len(data["constants"]) > 0


def test_admin_admins(client):
    r = client.get("/api/admin/admins")
    assert r.status_code == 200, r.text
    assert any(a["login"] == "owner" for a in r.json()["admins"])
