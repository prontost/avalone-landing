"""Data access for per-tenant user settings.

Table `money_user_settings` stores language, theme, layout and email per tenant.
"""

from __future__ import annotations

import sqlite3

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _finance_db  # resolve DB_PATH dynamically (tests patch it)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_user_settings (
    tenant INTEGER NOT NULL DEFAULT 1,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (tenant, key)
);
"""


class NotifyRepository(Repository):
    """SQL access to `money_user_settings`."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_finance_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.executescript(_SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(money_user_settings)")}
        if "tenant" not in cols:
            con.execute(
                "ALTER TABLE money_user_settings ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1"
            )
        return con

    def get_settings(self, tenant_id: int) -> dict:
        with self._conn() as con:
            rows = dict(
                con.execute(
                    "SELECT key, value FROM money_user_settings WHERE tenant=?",
                    (tenant_id,),
                ).fetchall()
            )
        return rows

    def set_settings(self, tenant_id: int, updates: dict) -> None:
        with self._conn() as con:
            for k, v in updates.items():
                con.execute(
                    "INSERT INTO money_user_settings (tenant, key, value) VALUES (?,?,?) "
                    "ON CONFLICT(tenant, key) DO UPDATE SET value=excluded.value",
                    (tenant_id, k, str(v)),
                )
