"""Data access for per-entry metadata and slept entries.

Tables:
- `money_entry_meta` — (tenant, entry, meta_key, meta_value)
- `money_slept_entries` — snapshots of entries cancelled when an account is disabled.
"""

from __future__ import annotations

import sqlite3

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _finance_db  # resolve DB_PATH dynamically (tests patch it)

_OCCURRED_KEY = "occurred_at"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_entry_meta (
    tenant      INTEGER NOT NULL,
    entry       TEXT NOT NULL,
    meta_key    TEXT NOT NULL,
    meta_value  TEXT NOT NULL,
    PRIMARY KEY (tenant, entry, meta_key)
);
CREATE TABLE IF NOT EXISTS money_slept_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL
);
"""


class EntryMetaRepository(Repository):
    """SQL access to entry metadata and slept entries."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_finance_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.executescript(_SCHEMA)
        # унифицированная БД могла создать money_slept_entries только с (tenant, name);
        # добиваем нужные Avalone Finance-колонки, если их ещё нет
        wanted = {
            "account": "TEXT NOT NULL",
            "debit": "TEXT NOT NULL",
            "credit": "TEXT NOT NULL",
            "amount": "REAL NOT NULL",
            "posting_date": "TEXT NOT NULL",
            "remark": "TEXT",
            "occurred_at": "TEXT",
        }
        existing = {r[1] for r in con.execute("PRAGMA table_info(money_slept_entries)")}
        for col, dtype in wanted.items():
            if col not in existing:
                con.execute(f"ALTER TABLE money_slept_entries ADD COLUMN {col} {dtype}")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_money_slept_account "
            "ON money_slept_entries(tenant, account)"
        )
        return con

    def set_occurred(self, tenant_id: int, voucher: str, occurred_at: str) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_entry_meta (tenant, entry, meta_key, meta_value) VALUES (?,?,?,?) "
                "ON CONFLICT(tenant, entry, meta_key) DO UPDATE SET meta_value=excluded.meta_value",
                (tenant_id, voucher, _OCCURRED_KEY, occurred_at),
            )

    def occurred_map(self, tenant_id: int, vouchers: list[str]) -> dict[str, str]:
        if not vouchers:
            return {}
        ph = ",".join("?" * len(vouchers))
        with self._conn() as con:
            rows = con.execute(
                f"SELECT entry, meta_value FROM money_entry_meta "
                f"WHERE tenant=? AND meta_key=? AND entry IN ({ph})",
                (tenant_id, _OCCURRED_KEY, *vouchers),
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def sleep_record(
        self, tenant_id: int, account: str, snap: dict, occurred_at: str | None
    ) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_slept_entries "
                "(tenant, account, debit, credit, amount, posting_date, remark, occurred_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    account,
                    snap["debit"],
                    snap["credit"],
                    snap["amount"],
                    snap["posting_date"],
                    snap.get("remark", ""),
                    occurred_at,
                ),
            )

    def sleeping_for(self, tenant_id: int, account: str) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT debit, credit, amount, posting_date, remark, occurred_at "
                "FROM money_slept_entries WHERE tenant=? AND account=?",
                (tenant_id, account),
            ).fetchall()
        return [
            {
                "debit": r[0],
                "credit": r[1],
                "amount": r[2],
                "posting_date": r[3],
                "remark": r[4],
                "occurred_at": r[5],
            }
            for r in rows
        ]

    def clear_sleeping(self, tenant_id: int, account: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM money_slept_entries WHERE tenant=? AND account=?",
                (tenant_id, account),
            )

    def forget(self, tenant_id: int, voucher: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM money_entry_meta WHERE tenant=? AND entry=? AND meta_key=?",
                (tenant_id, voucher, _OCCURRED_KEY),
            )
