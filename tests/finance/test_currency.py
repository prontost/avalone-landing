"""Cross-currency transfer guard."""
import asyncio
from datetime import date
from decimal import Decimal

import pytest


def _reset_db(tmp_path, monkeypatch):
    import avalone_finance.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import avalone_finance.core.tenant as tenant
    import avalone_finance.core.sqlledger as sl
    import avalone_finance.core.engine as engine
    import avalone_finance.core.global_settings as gs
    import avalone_finance.core.money as money
    importlib.reload(tenant)
    importlib.reload(sl)
    importlib.reload(engine)
    importlib.reload(gs)
    importlib.reload(money)
    tenant.set_current(1)
    return tenant


@pytest.fixture
def engine_env(tmp_path, monkeypatch):
    _reset_db(tmp_path, monkeypatch)
    import avalone_finance.core.tenant as tenant
    tenant.ensure_owner("owner", "ownerpass")


def test_transfer_between_different_currencies_fails(engine_env):
    from avalone_finance.core import engine, money

    async def run():
        krw = await engine.create_account("KRW Cash", None, "Asset", "Cash")
        usd = await engine.create_account("USD Cash", None, "Asset", "Cash")
        money.register(krw, "cash", 0, "KRW")
        money.register(usd, "cash", 1, "USD")
        with pytest.raises(engine.EngineError, match="разной валюты"):
            await engine.post_journal_entry(
                date.today(), "transfer", usd, krw, Decimal("100"))

    asyncio.run(run())


def test_transfer_between_same_currencies_ok(engine_env):
    from avalone_finance.core import engine, money

    async def run():
        krw1 = await engine.create_account("KRW Bank", None, "Asset", "Bank")
        krw2 = await engine.create_account("KRW Cash", None, "Asset", "Cash")
        money.register(krw1, "bank", 0, "KRW")
        money.register(krw2, "cash", 1, "KRW")
        name = await engine.post_journal_entry(
            date.today(), "transfer", krw2, krw1, Decimal("1000"))
        assert name.startswith("JE-")

    asyncio.run(run())
