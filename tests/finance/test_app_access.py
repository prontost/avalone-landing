"""Доступ пользователей к веткам платформы."""
import pytest


@pytest.fixture
def app_access(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    import avalone_finance.core.app_access as app_access
    importlib.reload(tenant)
    importlib.reload(app_access)
    return app_access, tenant


def test_default_public_app_accessible(app_access):
    aa, tenant = app_access
    tid = tenant.create_user("u1", "pw")
    assert "money" in aa.list_for_user(tid)
    assert aa.is_accessible(tid, "money") is True


def test_admin_can_revoke_access(app_access):
    aa, tenant = app_access
    tid = tenant.create_user("u2", "pw")
    aa.set_access(tid, "money", False)
    assert "money" not in aa.list_for_user(tid)
    assert aa.is_accessible(tid, "money") is False
    aa.set_access(tid, "money", True)
    assert aa.is_accessible(tid, "money") is True


def test_unknown_app_raises(app_access):
    aa, tenant = app_access
    tid = tenant.create_user("u3", "pw")
    with pytest.raises(ValueError):
        aa.set_access(tid, "nonexistent", True)


def test_grant_default_creates_rows(app_access):
    aa, tenant = app_access
    tid = tenant.create_user("u4", "pw")
    aa.grant_default(tid)
    admin_view = aa.list_for_admin(tid)
    money = next(a for a in admin_view if a["id"] == "money")
    assert money["enabled"] is True
