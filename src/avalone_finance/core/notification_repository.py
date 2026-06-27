"""Data access for the per-user notification log.

Table `money_notifications` stores notifications per tenant/app. Counta adds
`app`, `read_at`, `dismissed_at` columns if the unified schema does not yet
have them.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _counta_db  # resolve DB_PATH dynamically (tests patch it)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app          TEXT NOT NULL DEFAULT '',
    kind         TEXT DEFAULT 'info',
    title        TEXT NOT NULL,
    body         TEXT DEFAULT '',
    data         TEXT DEFAULT '{}',
    read         INTEGER DEFAULT 0,
    read_at      TEXT DEFAULT '',
    dismissed_at TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_money_notif_tenant_app ON money_notifications(tenant_id, app);
CREATE INDEX IF NOT EXISTS idx_money_notif_created ON money_notifications(created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationRepository(Repository):
    """SQL access to `money_notifications`."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_counta_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.row_factory = sqlite3.Row
        con.executescript(_SCHEMA)
        # унифицированная схема может не содержать app/read_at/dismissed_at
        wanted = {
            "app": "TEXT NOT NULL DEFAULT ''",
            "read_at": "TEXT DEFAULT ''",
            "dismissed_at": "TEXT DEFAULT ''",
        }
        existing = {r[1] for r in con.execute("PRAGMA table_info(money_notifications)")}
        for col, dtype in wanted.items():
            if col not in existing:
                con.execute(f"ALTER TABLE money_notifications ADD COLUMN {col} {dtype}")
        return con

    def add(
        self, tenant_id: int, app: str, title: str, body: str = "", kind: str = "info"
    ) -> int:
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO money_notifications (tenant_id, app, kind, title, body, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, app, kind, title, body, _now()),
            )
            return cur.lastrowid or 0

    def list_(
        self,
        tenant_id: int,
        app: str,
        filter: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Paginated notification list.

        filter:
          - all       — all non-dismissed
          - unread    — unread
          - read      — read
          - dismissed — dismissed/hidden
        """
        where = "tenant_id = ? AND app = ?"
        params: list = [tenant_id, app]

        if filter == "unread":
            where += " AND read_at = '' AND dismissed_at = ''"
        elif filter == "read":
            where += " AND read_at <> '' AND dismissed_at = ''"
        elif filter == "dismissed":
            where += " AND dismissed_at <> ''"
        else:  # all
            where += " AND dismissed_at = ''"

        with self._conn() as con:
            rows = con.execute(
                f"SELECT * FROM money_notifications WHERE {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            total = con.execute(
                f"SELECT COUNT(*) FROM money_notifications WHERE {where}",
                params,
            ).fetchone()[0]

        entries = [dict(r) for r in rows]
        return {
            "entries": entries,
            "total": total,
            "has_more": offset + len(entries) < total,
        }

    def mark_read(self, ids: list[int], tenant_id: int) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        with self._conn() as con:
            cur = con.execute(
                f"UPDATE money_notifications SET read=1, read_at = ? "
                f"WHERE tenant_id = ? AND id IN ({placeholders})",
                (_now(), tenant_id, *ids),
            )
            return cur.rowcount

    def mark_dismissed(self, ids: list[int], tenant_id: int) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        with self._conn() as con:
            cur = con.execute(
                f"UPDATE money_notifications SET dismissed_at = ? "
                f"WHERE tenant_id = ? AND id IN ({placeholders})",
                (_now(), tenant_id, *ids),
            )
            return cur.rowcount

    def count_unread(self, tenant_id: int, app: str) -> int:
        with self._conn() as con:
            row = con.execute(
                "SELECT COUNT(*) FROM money_notifications WHERE tenant_id = ? AND app = ? "
                "AND read_at = '' AND dismissed_at = ''",
                (tenant_id, app),
            ).fetchone()
        return row[0] if row else 0
