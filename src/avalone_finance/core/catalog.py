"""Canonical personal-finance categories + localized labels.

Categories are intentionally minimal (~12 expense + ~4 income) so that
analytics, tips and the 50/30/20 rule stay readable. Every category has a
role: need / want / goal."""

import sqlite3

from avalone_core import glossary_db as glossary

from avalone_finance.core.db import DB_PATH

# canonical EN account_name -> {root, role}. Display text lives in the unified
# glossary under cat_* keys (kind='category'); see canon_key() and seed_glossary().
CANON: dict[str, dict] = {
    # --- NEEDS ---
    "Housing": {"root": "Expense", "role": "need"},
    "Food": {"root": "Expense", "role": "need"},
    "Transport": {"root": "Expense", "role": "need"},
    "Health & wellness": {"root": "Expense", "role": "need"},
    "Family & kids": {"root": "Expense", "role": "need"},

    # --- WANTS ---
    "Eating out": {"root": "Expense", "role": "want"},
    "Shopping & stuff": {"root": "Expense", "role": "want"},
    "Fun & subscriptions": {"root": "Expense", "role": "want"},
    "Travel": {"root": "Expense", "role": "want"},
    "Other expense": {"root": "Expense", "role": "want"},
    "Uncategorized": {"root": "Expense", "role": "want"},

    # --- GOALS ---
    "Savings & investments": {"root": "Expense", "role": "goal"},
    "Debt repayment": {"root": "Expense", "role": "goal"},
    "Education & growth": {"root": "Expense", "role": "goal"},

    # --- INCOME ---
    "Salary income": {"root": "Income", "role": "income"},
    "Side income": {"root": "Income", "role": "income"},
    "Passive income": {"root": "Income", "role": "income"},
    "Other income": {"root": "Income", "role": "income"},
}

# Мультиюзер: переводы категорий у каждого тенанта свои. PK (tenant, account).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_catalog_i18n (
    tenant INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    ru TEXT, en TEXT, ko TEXT,
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
    cols = {r[1] for r in con.execute("PRAGMA table_info(money_catalog_i18n)")}
    if "tenant" not in cols:
        con.execute("ALTER TABLE money_catalog_i18n ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
    return con


def set_labels(account: str, ru: str, en: str, ko: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO money_catalog_i18n (tenant, account, ru, en, ko) VALUES (?,?,?,?,?) "
            "ON CONFLICT(tenant, account) DO UPDATE SET ru=excluded.ru, en=excluded.en, ko=excluded.ko",
            (_tid(), account, ru, en, ko))


def forget_labels(account: str) -> None:
    """Стереть переводы ярлыка из money_catalog_i18n (при окончательном удалении)."""
    with _conn() as con:
        con.execute("DELETE FROM money_catalog_i18n WHERE tenant=? AND account=?", (_tid(), account))


def _user_labels() -> dict[str, dict]:
    with _conn() as con:
        rows = con.execute("SELECT account, ru, en, ko FROM money_catalog_i18n WHERE tenant=?",
                           (_tid(),)).fetchall()
    return {r[0]: {"ru": r[1], "en": r[2], "ko": r[3]} for r in rows}


def label(account: str, account_name: str, lang: str = "ru") -> str:
    """Localized label for an account. Priority: user table -> canon -> glossary."""
    users = _user_labels()
    if account in users and users[account].get(lang):
        return users[account][lang]
    from avalone_finance.core import glossary
    if account.startswith("cat_"):
        g = glossary.get(account, lang)
        if g != account:
            return g
    base = account_name
    if base in CANON:
        key = canon_key(base)
        g = glossary.get(key, lang)
        if g != key:
            return g
    return account_name


def canon_key(account_name: str) -> str:
    """Нейтральный цифробуквенный ключ глоссария: 'Eating out' -> cat_eating_out."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", account_name.lower()).strip("_")
    return f"cat_{slug}"


def role(account_name: str) -> str:
    """Role of a canonical category: need | want | goal | income | ''."""
    meta = CANON.get(account_name)
    return meta.get("role", "") if meta else ""


def seed_glossary() -> int:
    """Засеять канонические категории/доходы в единый глоссарий (kind='category').

    Translations are taken from the unified glossary itself; this function only
    ensures the canonical cat_* keys are present with their metadata.
    """
    from avalone_finance.core import glossary
    rows = []
    for name, meta in CANON.items():
        is_income = meta.get("root") == "Income"
        role = meta.get("role", "")
        role_desc = {
            "need": "a basic need (must-have spending)",
            "want": "a lifestyle want (discretionary spending)",
            "goal": "a financial goal (savings, debt, self-investment)",
            "income": "an income source",
        }.get(role, "a personal finance category")
        key = canon_key(name)
        desc = (f"Name of {role_desc} in a personal finance app. "
                f"Canonical English term: '{name}'. "
                f"Translate as the natural everyday word a person uses for this.")
        rows.append({"key": key,
                     "ru": glossary.t(key, "ru"),
                     "en": glossary.t(key, "en"),
                     "ko": glossary.t(key, "ko"),
                     "kind": "category", "desc": desc})
    return glossary.upsert_many(rows)


def known_accounts() -> set[str]:
    """Полные имена счетов, у которых есть пользовательские переводы."""
    return set(_user_labels())


def is_user_category(account: str) -> bool:
    """Заведена ли пользователем (есть запись в money_catalog_i18n)."""
    return account in known_accounts()


# Базовый набор для нового пользователя.
DEFAULT_KEYS = [
    # needs
    "Housing", "Food", "Transport", "Health & wellness", "Family & kids",
    # wants
    "Eating out", "Shopping & stuff", "Fun & subscriptions", "Travel",
    "Other expense", "Uncategorized",
    # goals
    "Savings & investments", "Debt repayment", "Education & growth",
    # income
    "Salary income", "Side income", "Passive income", "Other income",
]


async def ensure_user_catalog() -> int:
    """Идемпотентно создать недостающие базовые категории в леджере
    и проставить им переводы. Возвращает число созданных."""
    import logging
    from avalone_finance.core import engine, sqlledger

    all_accs = await engine.list_accounts(leaf_only=False, include_disabled=True)
    pks = {a["name"] for a in all_accs}
    labelled = known_accounts()
    created = 0
    for key in DEFAULT_KEYS:
        meta = CANON[key]
        full = canon_key(key)
        if full not in pks:
            try:
                sqlledger.create_account_id(full, key, meta["root"])
                created += 1
            except Exception:
                logging.getLogger(__name__).warning("ensure_user_catalog: could not create %s", key)
                continue
        if full not in labelled:
            cat_key = canon_key(key)
            set_labels(full, glossary.t(cat_key, "ru"), glossary.t(cat_key, "en"), glossary.t(cat_key, "ko"))
    return created
