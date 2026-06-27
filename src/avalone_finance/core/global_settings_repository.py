"""Data access for instance-wide global settings.

Stored in the unified Avalone DB in `money_global_settings`.
Per-tenant settings live in `notify.user_settings`.
"""

from __future__ import annotations

import sqlite3

from avalone_core.database import Database, Repository

import avalone_finance.core.db as _counta_db  # resolve DB_PATH dynamically (tests patch it)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_global_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Дефолты перекрываются env при чтении через config.py, но здесь — фолбэк
# для runtime, когда в БД ещё ничего не записано.
DEFAULTS = {
    "registration_mode": "open",
    "registration_invite_code": "",
    "strict_password_policy": "false",
    "default_currency": "KRW",
    "web_base_url": "https://avalone.online/finance",
}


class GlobalSettingsRepository(Repository):
    """SQL access to `money_global_settings`."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database(_counta_db.DB_PATH))

    def _conn(self) -> sqlite3.Connection:
        con = self._db.connection()
        con.executescript(_SCHEMA)
        return con

    def get(self, key: str) -> str | None:
        """Return stored value or None if the key has never been set in DB."""
        with self._conn() as con:
            r = con.execute(
                "SELECT value FROM money_global_settings WHERE key=?", (key,)
            ).fetchone()
        return r[0] if r else None

    def set(self, key: str, value: str) -> None:
        """Upsert a global setting."""
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_global_settings (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def get_all(self) -> dict:
        """Return DEFAULTS merged with DB overrides."""
        with self._conn() as con:
            rows = dict(con.execute("SELECT key, value FROM money_global_settings").fetchall())
        return {**DEFAULTS, **rows}
