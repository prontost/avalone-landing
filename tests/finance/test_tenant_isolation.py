"""КРИТИЧНО: изоляция данных между тенантами (мультиюзер, этап 1).
Тенант А не должен видеть деньги/счета/проводки тенанта Б — ни на копейку.
"""
from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def sl(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    importlib.reload(tenant)
    import avalone_finance.core.sqlledger as sl
    importlib.reload(sl)
    return sl, tenant


def test_accounts_isolated(sl):
    led, tenant = sl
    tenant.set_current(1)
    led.create_account("Cash", None, "Asset", "Cash")
    tenant.set_current(2)
    led.create_account("Wallet", None, "Asset", "Cash")
    # каждый видит только свой счёт
    tenant.set_current(1)
    assert [a["account_name"] for a in led.list_accounts()] == ["Cash"]
    tenant.set_current(2)
    assert [a["account_name"] for a in led.list_accounts()] == ["Wallet"]


def test_balances_isolated(sl):
    led, tenant = sl
    tenant.set_current(1)
    cash1 = led.create_account("Cash", None, "Asset")
    cat1 = led.create_account("Food", None, "Expense")
    led.post_journal_entry(date(2026, 6, 1), "a", cat1, cash1, Decimal("100"))
    tenant.set_current(2)
    cash2 = led.create_account("Cash", None, "Asset")     # тот же PK у другого тенанта
    cat2 = led.create_account("Food", None, "Expense")
    led.post_journal_entry(date(2026, 6, 1), "b", cat2, cash2, Decimal("999"))
    # балансы НЕ смешиваются, хотя PK совпадают
    tenant.set_current(1)
    assert led.account_balance(cash1) == Decimal("-100")
    tenant.set_current(2)
    assert led.account_balance(cash2) == Decimal("-999")


def test_journal_isolated(sl):
    led, tenant = sl
    tenant.set_current(1)
    c1 = led.create_account("Cash", None, "Asset"); f1 = led.create_account("Food", None, "Expense")
    led.post_journal_entry(date(2026, 6, 1), "секрет-А", f1, c1, Decimal("50"))
    tenant.set_current(2)
    # тенант Б не видит проводку А ни в журнале, ни по счёту
    assert led.recent_entries(limit=99) == []
    assert led.entries_of_account(led.make_pk("Cash"), docstatus=(1, 2)) == []


def test_no_tenant_blocks_access(sl):
    led, tenant = sl
    tenant.set_current(0)   # не залогинен
    with pytest.raises(PermissionError):
        led.list_accounts()


def test_money_registry_isolated(sl):
    led, tenant = sl
    import importlib
    import avalone_finance.core.money as money
    importlib.reload(money)
    tenant.set_current(1)
    money.register("acc1", "bank", 0, currency="USD")
    tenant.set_current(2)
    money.register("acc1", "cash", 0, currency="KRW")   # тот же id, другой тенант
    tenant.set_current(1)
    assert money.account_currency("acc1") == "USD"
    assert list(money.registered()) == ["acc1"]
    tenant.set_current(2)
    assert money.account_currency("acc1") == "KRW"


def test_catalog_labels_isolated(sl):
    led, tenant = sl
    import importlib
    import avalone_finance.core.catalog as catalog
    importlib.reload(catalog)
    tenant.set_current(1)
    catalog.set_labels("x", "Аанглу", "Aenglu", "Akr")
    tenant.set_current(2)
    assert catalog.label("x", "x", "ru") == "x"      # тенант 2 не видит метку тенанта 1
    tenant.set_current(1)
    assert catalog.label("x", "x", "ru") == "Аанглу"


def test_settings_isolated(sl):
    led, tenant = sl
    import importlib
    import avalone_finance.core.notify as notify
    importlib.reload(notify)
    tenant.set_current(1)
    notify.set_settings({"lang": "en"})
    tenant.set_current(2)
    assert notify.get_settings()["lang"] == "auto"     # дефолт, не "en" тенанта 1
    tenant.set_current(1)
    assert notify.get_settings()["lang"] == "en"


def test_password_reset_token_flow(sl):
    """Сброс пароля по токену: поиск по почте, одноразовость, срок, смена пароля."""
    from datetime import datetime, timedelta, timezone
    led, tenant = sl
    tid = tenant.create_user("bob", "oldpass", "bob@example.com")
    # поиск аккаунтов по почте (для восстановления логина/сброса)
    accs = tenant.accounts_for_email("BOB@example.com")   # регистронезависимо
    assert [a["login"] for a in accs] == ["bob"]
    assert tenant.accounts_for_email("nobody@x.com") == []
    # валидный токен → гасится при первом использовании (одноразовость)
    exp = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
    tenant.set_reset_token(tid, "tok-123", exp)
    assert tenant.consume_reset_token("tok-123") == tid
    assert tenant.consume_reset_token("tok-123") is None   # повторно — нельзя
    # истёкший токен не принимается
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    tenant.set_reset_token(tid, "tok-old", past)
    assert tenant.consume_reset_token("tok-old") is None
    assert tenant.consume_reset_token("") is None
    # принудительная смена пароля (после токена, без старого)
    tenant.set_password(tid, "newpass1")
    assert tenant.authenticate("bob", "newpass1") == tid
    assert tenant.authenticate("bob", "oldpass") is None


def test_password_auth_roundtrip(sl):
    """РЕГРЕССИЯ: hash→verify→authenticate должны работать (был баг
    hashlib.compare_digest вместо hmac → всегда False, никто не входил)."""
    led, tenant = sl
    tenant.create_user("alice", "secret123", "")
    assert tenant.verify_password("secret123", tenant.hash_password("secret123"))
    assert tenant.authenticate("alice", "secret123") is not None
    assert tenant.authenticate("alice", "wrong") is None
