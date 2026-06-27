"""Собственный двойной леджер в counta.db (SQLite) — замена ERPNext-движка.

Цель переезда (Дэн, 2026-06-16): зависеть от ERPNext по минимуму, в итоге уйти
совсем. ERPNext делал для нас 3 вещи — план счетов, проводки (двойная запись),
балансы. Всё это здесь, на нашем SQLite, рядом с money_accounts/catalog_i18n.

Контракт намеренно повторяет сигнатуры `core/erpnext.py`, чтобы переключение шло
за единым фасадом с минимальными правками вызовов (см. шаг 3 переезда).

(Отдельный модуль от заброшенного core/ledger.py — тот на SQLAlchemy/Postgres и
Telegram-тенантах, мёртвый. Здесь — SQLite, single-user, в нашей counta.db.)

Модель:
- money_led_accounts: name(PK, "Имя - DP"), account_name, root_type
  (Asset|Liability|Equity|Income|Expense), account_type, is_group, disabled.
- money_led_entries: проводка. docstatus 1=активна, 2=отменена.
- money_led_lines: строки. Инвариант sum(debit)==sum(credit) на проводку; CHECK строки.

ВАЖНО (требование Дэна): окончательное удаление здесь ТРИВИАЛЬНО — DELETE строк,
без «надгробий»-призраков, в отличие от append-only ERPNext.
"""

import sqlite3
from datetime import date, datetime
from decimal import Decimal

from avalone_core import glossary_db as glossary
from avalone_finance.core.db import DB_PATH

ABBR = "DP"   # суффикс PK счёта (наследие компании Denis Personal — совместимость)

# Мультиюзер: каждая строка принадлежит tenant. PK счёта/проводки уникальны в
# пределах тенанта (composite), не глобально — у разных юзеров может быть свой
# cat_groceries. Все запросы фильтруются по tenant.current() (см. core/tenant).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_led_accounts (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    account_name TEXT NOT NULL,
    root_type    TEXT NOT NULL,
    account_type TEXT DEFAULT '',
    is_group     INTEGER DEFAULT 0,
    disabled     INTEGER DEFAULT 0,
    PRIMARY KEY (tenant, name)
);
CREATE TABLE IF NOT EXISTS money_led_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    posting_date TEXT NOT NULL,
    user_remark  TEXT DEFAULT '',
    total_debit  REAL NOT NULL DEFAULT 0,
    docstatus    INTEGER NOT NULL DEFAULT 1,
    creation     TEXT NOT NULL,
    PRIMARY KEY (tenant, name)
);
CREATE TABLE IF NOT EXISTS money_led_lines (
    tenant  INTEGER NOT NULL DEFAULT 1,
    entry   TEXT NOT NULL,
    account TEXT NOT NULL,
    debit   REAL NOT NULL DEFAULT 0,
    credit  REAL NOT NULL DEFAULT 0,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);
CREATE INDEX IF NOT EXISTS idx_money_led_lines_entry   ON money_led_lines(tenant, entry);
CREATE INDEX IF NOT EXISTS idx_money_led_lines_account ON money_led_lines(tenant, account);
CREATE INDEX IF NOT EXISTS idx_money_led_entries_status ON money_led_entries(tenant, docstatus, posting_date);
CREATE TABLE IF NOT EXISTS money_led_seq (tenant INTEGER NOT NULL, year TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (tenant, year));
"""


class LedgerError(Exception):
    pass


def _tid() -> int:
    """Текущий тенант. Без установленного — ошибка (защита от утечки данных)."""
    from avalone_finance.core import tenant
    return tenant.require_current()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=OFF")   # FK на composite не нужны — чистим вручную
    con.executescript(_SCHEMA)
    # миграция старых однопользовательских таблиц: добить колонку tenant=1
    for tbl in ("money_led_accounts", "money_led_entries", "money_led_lines", "money_led_seq"):
        try:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({tbl})")}
            if "tenant" not in cols:
                con.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass
    return con


def _next_voucher(con: sqlite3.Connection, tid: int) -> str:
    year = str(datetime.now().year)
    row = con.execute("SELECT n FROM money_led_seq WHERE tenant=? AND year=?", (tid, year)).fetchone()
    n = (row[0] if row else 0) + 1
    prefix = f"JE-{year}-"
    # защита от коллизий: если в базе уже есть проводки с таким номером
    # (например, после миграции), берём следующий свободный.
    while con.execute(
        "SELECT 1 FROM money_led_entries WHERE tenant=? AND name=?",
        (tid, f"{prefix}{n:05d}")
    ).fetchone():
        n += 1
    con.execute("INSERT INTO money_led_seq (tenant, year, n) VALUES (?,?,?) "
                "ON CONFLICT(tenant, year) DO UPDATE SET n=excluded.n", (tid, year, n))
    return f"{prefix}{n:05d}"


# ----------------------------------------------------------------- счета
def make_pk(account_name: str) -> str:
    return f"{account_name} - {ABBR}"


def list_accounts(*, leaf_only: bool = True, include_disabled: bool = False) -> list[dict]:
    tid = _tid()
    q = ("SELECT name, account_name, root_type, account_type, is_group, disabled "
         "FROM money_led_accounts WHERE tenant=?")
    if leaf_only:
        q += " AND is_group=0"
    if not include_disabled:
        q += " AND disabled=0"
    with _conn() as con:
        rows = con.execute(q, (tid,)).fetchall()
    return [{"name": r[0], "account_name": r[1], "root_type": r[2],
             "account_type": r[3], "is_group": r[4], "disabled": r[5]} for r in rows]


def create_account(account_name: str, parent_account: str | None,
                   root_type: str, account_type: str = "") -> str:
    return create_account_id(make_pk(account_name), account_name, root_type, account_type)


def create_account_id(account_id: str, account_name: str, root_type: str,
                      account_type: str = "") -> str:
    """Создать счёт с ЯВНЫМ id (нейтральный ключ cat_<slug>). Идемпотентно, в
    пределах текущего тенанта."""
    tid = _tid()
    with _conn() as con:
        con.execute(
            "INSERT INTO money_led_accounts (tenant, name, account_name, root_type, account_type, is_group, disabled) "
            "VALUES (?,?,?,?,?,0,0) ON CONFLICT(tenant, name) DO NOTHING",
            (tid, account_id, account_name, root_type, account_type))
    return account_id


def upsert_account(name: str, account_name: str, root_type: str,
                   account_type: str = "", is_group: int = 0, disabled: int = 0,
                   tenant: int | None = None) -> None:
    """Прямой апсерт счёта с готовым PK — для миграции. tenant можно задать явно."""
    tid = tenant if tenant is not None else _tid()
    with _conn() as con:
        con.execute(
            "INSERT INTO money_led_accounts (tenant, name, account_name, root_type, account_type, is_group, disabled) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant, name) DO UPDATE SET "
            "account_name=excluded.account_name, root_type=excluded.root_type, "
            "account_type=excluded.account_type, is_group=excluded.is_group, "
            "disabled=excluded.disabled",
            (tid, name, account_name, root_type, account_type, is_group, disabled))


def disable_account(name: str) -> None:
    with _conn() as con:
        con.execute("UPDATE money_led_accounts SET disabled=1 WHERE tenant=? AND name=?", (_tid(), name))


def enable_account(name: str) -> None:
    with _conn() as con:
        con.execute("UPDATE money_led_accounts SET disabled=0 WHERE tenant=? AND name=?", (_tid(), name))


def delete_account(name: str) -> None:
    tid = _tid()
    with _conn() as con:
        used = con.execute("SELECT COUNT(*) FROM money_led_lines WHERE tenant=? AND account=?",
                           (tid, name)).fetchone()[0]
        if used:
            raise LedgerError(
                glossary.t("error_account_still_used", lang="ru")
                .replace("{name}", name)
                .replace("{used}", str(used))
            )
        con.execute("DELETE FROM money_led_accounts WHERE tenant=? AND name=?", (tid, name))


def group_parent(root_type: str) -> str | None:
    return None   # плоская модель — групп нет


# ----------------------------------------------------------------- проводки
def post_journal_entry(entry_date: date, remark: str, debit_account: str,
                       credit_account: str, amount: Decimal, *,
                       name: str | None = None, creation: str | None = None,
                       tenant: int | None = None) -> str:
    """Сбалансированная 2-строчная проводка (debit==credit). Возвращает PK.
    name/creation/tenant — для миграции."""
    amt = round(float(amount), 2)
    if amt <= 0:
        raise LedgerError(glossary.t("error_amount_must_be_positive", lang="ru"))
    tid = tenant if tenant is not None else _tid()
    now = creation or datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        nm = name or _next_voucher(con, tid)
        con.execute(
            "INSERT INTO money_led_entries (tenant, name, posting_date, user_remark, total_debit, docstatus, creation) "
            "VALUES (?,?,?,?,?,1,?)",
            (tid, nm, entry_date.isoformat(), remark, amt, now))
        con.execute("INSERT INTO money_led_lines (tenant, entry, account, debit, credit) VALUES (?,?,?,?,0)",
                    (tid, nm, debit_account, amt))
        con.execute("INSERT INTO money_led_lines (tenant, entry, account, debit, credit) VALUES (?,?,?,0,?)",
                    (tid, nm, credit_account, amt))
    return nm


def cancel_journal_entry(name: str) -> None:
    with _conn() as con:
        con.execute("UPDATE money_led_entries SET docstatus=2 WHERE tenant=? AND name=?", (_tid(), name))


def restore_cancelled(name: str) -> None:
    """Вернуть отменённую (docstatus 2->1) НАПРЯМУЮ — отмена обратима."""
    with _conn() as con:
        con.execute("UPDATE money_led_entries SET docstatus=1 WHERE tenant=? AND name=?", (_tid(), name))


def set_status(name: str, docstatus: int, tenant: int | None = None) -> None:
    tid = tenant if tenant is not None else _tid()
    with _conn() as con:
        con.execute("UPDATE money_led_entries SET docstatus=? WHERE tenant=? AND name=?",
                    (docstatus, tid, name))


def delete_entry(name: str) -> None:
    """Удалить проводку НАВСЕГДА (строки + проводку). Без призраков."""
    tid = _tid()
    with _conn() as con:
        con.execute("DELETE FROM money_led_lines WHERE tenant=? AND entry=?", (tid, name))
        con.execute("DELETE FROM money_led_entries WHERE tenant=? AND name=?", (tid, name))


def entry_accounts(name: str) -> tuple[str, str] | None:
    with _conn() as con:
        rows = con.execute(
            "SELECT account, debit, credit FROM money_led_lines WHERE tenant=? AND entry=?",
            (_tid(), name)).fetchall()
    debit = next((r[0] for r in rows if r[1]), None)
    credit = next((r[0] for r in rows if r[2]), None)
    return (debit, credit) if debit and credit else None


def entry_detail(name: str) -> dict | None:
    tid = _tid()
    with _conn() as con:
        e = con.execute("SELECT posting_date, user_remark FROM money_led_entries WHERE tenant=? AND name=?",
                        (tid, name)).fetchone()
        if not e:
            return None
        rows = con.execute("SELECT account, debit, credit FROM money_led_lines WHERE tenant=? AND entry=?",
                           (tid, name)).fetchall()
    debit = next((r[0] for r in rows if r[1]), None)
    credit = next((r[0] for r in rows if r[2]), None)
    amount = next((r[1] for r in rows if r[1]), 0)
    if not (debit and credit):
        return None
    return {"debit": debit, "credit": credit, "amount": float(amount),
            "posting_date": e[0], "remark": e[1] or ""}


def entries_of_account(account: str, docstatus: tuple[int, ...] = (1,)) -> list[str]:
    tid = _tid()
    ph = ",".join("?" * len(docstatus))
    with _conn() as con:
        rows = con.execute(
            f"SELECT DISTINCT l.entry FROM money_led_lines l JOIN money_led_entries e "
            f"ON e.tenant=l.tenant AND e.name=l.entry "
            f"WHERE l.tenant=? AND l.account=? AND e.docstatus IN ({ph})",
            (tid, account, *docstatus)).fetchall()
    return [r[0] for r in rows]


def entry_counts(account_names: list[str]) -> dict[str, int]:
    if not account_names:
        return {}
    tid = _tid()
    ph = ",".join("?" * len(account_names))
    with _conn() as con:
        rows = con.execute(
            f"SELECT l.account, COUNT(DISTINCT l.entry) FROM money_led_lines l "
            f"JOIN money_led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
            f"WHERE l.tenant=? AND l.account IN ({ph}) AND e.docstatus=1 GROUP BY l.account",
            (tid, *account_names)).fetchall()
    return {r[0]: r[1] for r in rows}


def account_balance(account: str, on_date: date | None = None) -> Decimal:
    """Баланс = sum(debit)-sum(credit) по активным проводкам тенанта. Знак: +
    есть деньги, − долг."""
    tid = _tid()
    q = ("SELECT COALESCE(SUM(l.debit-l.credit),0) FROM money_led_lines l "
         "JOIN money_led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
         "WHERE l.tenant=? AND l.account=? AND e.docstatus=1")
    params: list = [tid, account]
    if on_date:
        q += " AND e.posting_date<=?"
        params.append(on_date.isoformat())
    with _conn() as con:
        v = con.execute(q, params).fetchone()[0]
    return Decimal(str(v or 0))


def recent_entries(limit: int = 10, *, extra_filters: list | None = None,
                   order_by: str = "posting_date desc, name desc",
                   docstatus: tuple[int, ...] = (1,)) -> list[dict]:
    tid = _tid()
    ph = ",".join("?" * len(docstatus))
    where = ["tenant=?", f"docstatus IN ({ph})"]
    params: list = [tid, *docstatus]
    for f in (extra_filters or []):
        field, op, val = f[0], f[1], f[2]
        col = {"posting_date": "posting_date", "creation": "creation",
               "total_debit": "total_debit"}.get(field)
        if not col or op not in (">=", "<=", ">", "<", "=", "!="):
            continue
        where.append(f"{col} {op} ?")
        params.append(val)
    safe_order = order_by if all(c.isalnum() or c in " ,_" for c in order_by) else "posting_date desc"
    q = ("SELECT name, posting_date, user_remark, total_debit, creation, docstatus "
         f"FROM money_led_entries WHERE {' AND '.join(where)} ORDER BY {safe_order} LIMIT ?")
    params.append(limit)
    with _conn() as con:
        rows = con.execute(q, params).fetchall()
    return [{"name": r[0], "posting_date": r[1], "user_remark": r[2],
             "total_debit": r[3], "creation": r[4], "docstatus": r[5]} for r in rows]


def find_entry(keywords: str, limit: int = 30) -> dict | None:
    words = [w.lower() for w in keywords.split() if len(w) > 2]
    for r in recent_entries(limit=limit):
        rem = (r.get("user_remark") or "").lower()
        if any(w in rem for w in words):
            return r
    return None


# --------------------------------------------------------------- целостность
def assert_balanced(tenant: int | None = None) -> int:
    """Инвариант двойной записи. Если tenant задан — по нему; иначе по текущему
    (для миграции можно проверить конкретный). Глобально debit==credit тоже."""
    tid = tenant if tenant is not None else (_tid() if _has_tenant() else None)
    with _conn() as con:
        base = "FROM money_led_lines"
        params: list = []
        if tid is not None:
            base += " WHERE tenant=?"; params = [tid]
        bad = con.execute(
            f"SELECT entry, SUM(debit), SUM(credit) {base} GROUP BY entry "
            "HAVING ROUND(SUM(debit),2)<>ROUND(SUM(credit),2)", params).fetchall()
        if bad:
            raise LedgerError(
                glossary.t("error_unbalanced_entries", lang="ru").replace("{bad}", str(bad[:5]))
            )
        gd, gc = con.execute(
            f"SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) {base}", params).fetchone()
        n = con.execute(
            "SELECT COUNT(*) FROM money_led_entries" + (" WHERE tenant=?" if tid is not None else ""),
            params).fetchone()[0]
    if round(gd, 2) != round(gc, 2):
        raise LedgerError(
            glossary.t("error_global_imbalance", lang="ru")
            .replace("{gd}", str(gd))
            .replace("{gc}", str(gc))
        )
    return n


def _has_tenant() -> bool:
    from avalone_finance.core import tenant
    return bool(tenant.current())
