"""Global settings: owner can change registration mode, non-owner cannot."""
import pytest


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    import avalone_finance.core.global_settings as global_settings
    import avalone_finance.core.config as config
    importlib.reload(tenant)
    importlib.reload(global_settings)
    importlib.reload(config)
    return tenant, global_settings, config


def test_admin_can_change_registration_mode(ctx):
    tenant, gs, config = ctx
    tenant.ensure_owner("owner", "ownerpass")
    tenant.add_admin(tenant.OWNER_TENANT_ID)
    tenant.set_current(tenant.OWNER_TENANT_ID)
    gs.set("registration_mode", "invite")
    assert config.registration_mode() == "invite"


def test_non_owner_cannot_change_global_settings(ctx):
    tenant, gs, config = ctx
    tenant.ensure_owner("owner", "ownerpass")
    tid = tenant.create_user("user", "pass", "")
    tenant.set_current(tid)
    with pytest.raises(PermissionError):
        gs.set("registration_mode", "closed")


def test_registration_mode_env_fallback(ctx, monkeypatch):
    tenant, gs, config = ctx
    # no DB value set, should fall back to env default
    monkeypatch.setenv("AVALONE_REGISTRATION_MODE", "closed")
    import importlib
    importlib.reload(config)
    assert config.registration_mode() == "closed"


def test_invite_code_rotation(ctx):
    tenant, gs, config = ctx
    tenant.ensure_owner("owner", "ownerpass")
    tenant.add_admin(tenant.OWNER_TENANT_ID)
    tenant.set_current(tenant.OWNER_TENANT_ID)
    gs.set("registration_invite_code", "new-secret")
    assert config.registration_invite_code() == "new-secret"
