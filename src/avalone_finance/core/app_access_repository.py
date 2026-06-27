"""Data access for per-user app access permissions.

Table `money_user_apps` stores explicit overrides for the in-code app registry.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _counta_db  # resolve DB_PATH dynamically (tests patch it)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_user_apps (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_id     TEXT NOT NULL,
    enabled    INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, app_id)
);
CREATE INDEX IF NOT EXISTS idx_money_user_apps_enabled ON money_user_apps(user_id, enabled);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppAccessRepository(Repository):
    """SQL access to `money_user_apps`."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_counta_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.row_factory = sqlite3.Row
        con.executescript(_SCHEMA)
        return con

    def rows_for(self, user_id: int) -> dict[str, bool]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT app_id, enabled FROM money_user_apps WHERE user_id=?", (user_id,)
            ).fetchall()
        return {r["app_id"]: bool(r["enabled"]) for r in rows}

    def set_access(self, user_id: int, app_id: str, enabled: bool) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO money_user_apps (user_id, app_id, enabled, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, app_id) DO UPDATE SET enabled=excluded.enabled
                """,
                (user_id, app_id, 1 if enabled else 0, _now()),
            )

    def delete_for_user(self, user_id: int) -> None:
        """Delete all access records for a user (used by tenant.delete_user)."""
        with self._conn() as con:
            con.execute("DELETE FROM money_user_apps WHERE user_id=?", (user_id,))
