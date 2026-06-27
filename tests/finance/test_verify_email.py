"""Email verification: code generation, expiry, and verification status."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def tenant(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    importlib.reload(tenant)
    return tenant


def test_verify_code_success(tenant):
    tid = tenant.create_user("alice", "secret", "alice@example.com")
    tenant.set_verify_code(tid, "123456")
    assert tenant.check_verify_code(tid, "123456") is True
    u = tenant.get_user(tid)
    assert u["email_verified"] == 1


def test_verify_code_wrong(tenant):
    tid = tenant.create_user("bob", "secret", "bob@example.com")
    tenant.set_verify_code(tid, "123456")
    assert tenant.check_verify_code(tid, "000000") is False
    assert tenant.get_user(tid)["email_verified"] == 0


def test_verify_code_expired(tenant, monkeypatch):
    tid = tenant.create_user("carol", "secret", "carol@example.com")
    tenant.set_verify_code(tid, "123456")

    # эмулируем, что код был отправлен 31 минуту назад
    old = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(timespec="seconds")
    with tenant._conn() as con:
        con.execute("UPDATE users SET verify_sent=? WHERE id=?", (old, tid))

    assert tenant.check_verify_code(tid, "123456") is False
    assert tenant.get_user(tid)["email_verified"] == 0


def test_verify_code_empty(tenant):
    tid = tenant.create_user("dave", "secret", "dave@example.com")
    assert tenant.check_verify_code(tid, "") is False
    assert tenant.check_verify_code(tid, "   ") is False


def test_set_email_resets_verified(tenant):
    tid = tenant.create_user("eve", "secret", "eve@example.com")
    tenant.set_verify_code(tid, "123456")
    tenant.check_verify_code(tid, "123456")
    assert tenant.get_user(tid)["email_verified"] == 1

    tenant.set_email(tid, "new@example.com")
    u = tenant.get_user(tid)
    assert u["email"] == "new@example.com"
    assert u["email_verified"] == 0
