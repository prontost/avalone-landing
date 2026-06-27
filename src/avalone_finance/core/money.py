"""Реестр денежных счетов пользователя (касса / банк / карты / будущие).

Зачем отдельный реестр, а не эвристика по имени/типу:
ERPNext не размечает «деньги» надёжно — у заведённых счетов `account_type` пуст
(Банк KB, кредитка SAMSUNG = ''), родительские группы непоследовательны (кредитка
под «Duties and Taxes»), а keyword-эвристика ломается на системных счетах
(«Creditors» ловит "credit", «Bank Overdraft» — "bank") и показывала лишь ОДИН
счёт на тип. Из-за этого кредитка «работала» лишь случайно (имя совпало), а любой
будущий счёт в форму бы не попал.

Решение по образцу catalog_i18n: денежные счета — явный реестр. Любой счёт в
реестре — полноценный денежный, одинаково с банком, кредиткой и будущими. Плюс
безусловно включаем счета с нативным ERPNext-типом Bank/Cash (две надёжные двери).
"""

import sqlite3

from avalone_finance.core.db import DB_PATH

# account_type, которые сам ERPNext трактует как деньги — включаем безусловно
NATIVE_MONEY_TYPES = {"Bank", "Cash"}

# База — KRW; но «валюты по умолчанию НЕТ» в смысле UX: при создании счёта
# Дэн выбирает валюту явно. KRW лишь страховка для уже существующих записей.
DEFAULT_CURRENCY = "KRW"

# Мультиюзер: реестр у каждого тенанта свой. PK композитный (tenant, account);
# все запросы фильтруются по tenant.current() — забытый фильтр = чужие счета.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_money_accounts (
    tenant INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,      -- стабильный id счёта
    kind TEXT,                  -- cash | bank | credit_card | other
    ord INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'KRW',
    label TEXT,
    PRIMARY KEY (tenant, account)
);
"""


def _tid() -> int:
    from avalone_finance.core import tenant
    return tenant.require_current()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(money_money_accounts)")}
    if "currency" not in cols:
        con.execute("ALTER TABLE money_money_accounts ADD COLUMN currency TEXT DEFAULT 'KRW'")
    if "label" not in cols:
        con.execute("ALTER TABLE money_money_accounts ADD COLUMN label TEXT")
    if "tenant" not in cols:
        con.execute("ALTER TABLE money_money_accounts ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
    return con


def set_label(account: str, label: str) -> None:
    with _conn() as con:
        con.execute("UPDATE money_money_accounts SET label=? WHERE tenant=? AND account=?",
                    (label.strip(), _tid(), account))


def account_label(account: str) -> str | None:
    with _conn() as con:
        row = con.execute("SELECT label FROM money_money_accounts WHERE tenant=? AND account=?",
                          (_tid(), account)).fetchone()
    return (row[0] if row and row[0] else None)


def register(account: str, kind: str = "other", ord: int = 0,
             currency: str | None = None) -> None:
    cur = (currency or DEFAULT_CURRENCY).upper()
    tid = _tid()
    with _conn() as con:
        con.execute(
            "INSERT INTO money_money_accounts (tenant, account, kind, ord, currency) VALUES (?,?,?,?,?) "
            "ON CONFLICT(tenant, account) DO UPDATE SET kind=excluded.kind, ord=excluded.ord"
            + ("" if currency is None else ", currency=excluded.currency"),
            (tid, account, kind, ord, cur))


def set_currency(account: str, currency: str) -> None:
    with _conn() as con:
        con.execute("UPDATE money_money_accounts SET currency=? WHERE tenant=? AND account=?",
                    (currency.upper(), _tid(), account))


def unregister(account: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM money_money_accounts WHERE tenant=? AND account=?", (_tid(), account))


def registered() -> dict[str, str]:
    """{account_pk: kind} денежных счетов ТЕКУЩЕГО тенанта в порядке показа (ord)."""
    with _conn() as con:
        return {r[0]: r[1] for r in
                con.execute("SELECT account, kind FROM money_money_accounts "
                            "WHERE tenant=? ORDER BY ord, account", (_tid(),)).fetchall()}


def registered_full() -> dict[str, dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT account, kind, ord, currency FROM money_money_accounts "
            "WHERE tenant=? ORDER BY ord, account", (_tid(),)).fetchall()
    return {r[0]: {"kind": r[1], "ord": r[2], "currency": r[3] or DEFAULT_CURRENCY}
            for r in rows}


def account_currency(account: str) -> str:
    with _conn() as con:
        row = con.execute("SELECT currency FROM money_money_accounts WHERE tenant=? AND account=?",
                          (_tid(), account)).fetchone()
    return (row[0] if row and row[0] else DEFAULT_CURRENCY)


def is_money(account: str, account_type: str | None = None) -> bool:
    """Денежный ли счёт: в реестре ИЛИ нативный Bank/Cash тип ERPNext."""
    if account_type in NATIVE_MONEY_TYPES:
        return True
    return account in registered()


async def ensure_money_seed() -> int:
    """Идемпотентно засеять реестр текущими денежными счетами, чтобы при переходе
    с keyword-логики ничего не пропало. Сеется ровно один раз (пока реестр пуст);
    далее пополняется явной регистрацией новых счетов. Возвращает число засеянных."""
    if registered():
        return 0
    from avalone_finance.core import engine, ledger_ops
    accounts = await engine.list_accounts()
    n = 0
    for kind in ("cash", "bank", "credit_card"):
        acc = ledger_ops.resolve_money_account(kind, accounts)
        if acc:
            register(acc, kind, n)
            n += 1
    return n
