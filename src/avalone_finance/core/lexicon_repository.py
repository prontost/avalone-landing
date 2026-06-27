"""Data access for the per-user learned lexicon.

Table `money_lexicon` maps normalized user phrases to ERPNext account names.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _counta_db  # resolve DB_PATH dynamically (tests patch it)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_lexicon (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    phrase TEXT NOT NULL,
    account TEXT NOT NULL,
    ts TEXT NOT NULL,
    UNIQUE(chat_id, kind, phrase)
);
"""


class LexiconRepository(Repository):
    """SQL access to `money_lexicon`."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_counta_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.executescript(_SCHEMA)
        return con

    def lookup(self, chat_id: int, kind: str, normalized: str) -> str | None:
        """Return an account for a normalized phrase, using exact/containment match."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT phrase, account FROM money_lexicon WHERE chat_id=? AND kind=? "
                "ORDER BY length(phrase) DESC",
                (chat_id, kind),
            ).fetchall()
        for saved, account in rows:
            if saved == normalized or saved in normalized or normalized in saved:
                return account
        return None

    def save(self, chat_id: int, kind: str, normalized: str, account: str) -> None:
        """Upsert a normalized phrase -> account mapping."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_lexicon (chat_id, kind, phrase, account, ts) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(chat_id, kind, phrase) "
                "DO UPDATE SET account=excluded.account, ts=excluded.ts",
                (chat_id, kind, normalized, account, now),
            )
