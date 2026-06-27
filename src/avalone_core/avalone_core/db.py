"""Unified SQLite database for the Avalone platform.

All platform data lives in a single file. Modules use prefixed tables:
- users, sessions
- money_accounts, money_led_entries, ...
- work_trips, work_trip_members, ...
"""

import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".avalone" / "avalone.db"
DB_PATH: Path = DEFAULT_DB_PATH


def configure(path: str | Path | None = None) -> None:
    global DB_PATH
    if path:
        DB_PATH = Path(path)
    elif os.environ.get("AVALONE_DB_PATH"):
        DB_PATH = Path(os.environ["AVALONE_DB_PATH"])
    else:
        DB_PATH = DEFAULT_DB_PATH


def connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _execute_script(con: sqlite3.Connection, sql: str) -> None:
    con.executescript(sql)
    con.commit()


SCHEMA = """
-- Users & sessions (single source of truth)
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    login          TEXT UNIQUE NOT NULL,
    pwhash         TEXT NOT NULL,
    email          TEXT DEFAULT '',
    email_verified INTEGER DEFAULT 0,
    verify_code    TEXT DEFAULT '',
    verify_sent    TEXT DEFAULT '',
    reset_token    TEXT DEFAULT '',
    reset_expires  TEXT DEFAULT '',
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Admins (module column distinguishes 'money'/'work')
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module  TEXT NOT NULL DEFAULT 'money',
    PRIMARY KEY (user_id, module)
);

-- Money module (Counta)
CREATE TABLE IF NOT EXISTS money_global_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS money_led_seq (
    tenant INTEGER NOT NULL,
    year   TEXT NOT NULL,
    n      INTEGER NOT NULL,
    PRIMARY KEY (tenant, year)
);

CREATE TABLE IF NOT EXISTS money_catalog_i18n (
    tenant  INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    ru      TEXT,
    en      TEXT,
    ko      TEXT,
    PRIMARY KEY (tenant, account)
);

CREATE TABLE IF NOT EXISTS money_money_accounts (
    tenant   INTEGER NOT NULL DEFAULT 1,
    account  TEXT NOT NULL,
    kind     TEXT,
    ord      INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'KRW',
    label    TEXT,
    PRIMARY KEY (tenant, account)
);

CREATE TABLE IF NOT EXISTS money_glossary (
    key  TEXT PRIMARY KEY,
    ru   TEXT,
    en   TEXT,
    ko   TEXT,
    kind TEXT DEFAULT 'ui',
    desc TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS money_user_settings (
    tenant INTEGER NOT NULL DEFAULT 1,
    key    TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (tenant, key)
);

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

CREATE TABLE IF NOT EXISTS money_entry_meta (
    tenant      INTEGER NOT NULL,
    entry       TEXT NOT NULL,
    meta_key    TEXT NOT NULL,
    meta_value  TEXT NOT NULL,
    PRIMARY KEY (tenant, entry, meta_key)
);

CREATE TABLE IF NOT EXISTS money_slept_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    account      TEXT,
    debit        TEXT,
    credit       TEXT,
    amount       REAL,
    posting_date TEXT,
    remark       TEXT,
    occurred_at  TEXT,
    PRIMARY KEY (tenant, name)
);

-- Work module
CREATE TABLE IF NOT EXISTS work_global_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_led_accounts (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    account_name TEXT NOT NULL,
    root_type    TEXT NOT NULL,
    account_type TEXT DEFAULT '',
    is_group     INTEGER DEFAULT 0,
    disabled     INTEGER DEFAULT 0,
    PRIMARY KEY (tenant, name)
);

CREATE TABLE IF NOT EXISTS work_led_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    posting_date TEXT NOT NULL,
    user_remark  TEXT DEFAULT '',
    total_debit  REAL NOT NULL DEFAULT 0,
    docstatus    INTEGER NOT NULL DEFAULT 1,
    creation     TEXT NOT NULL,
    PRIMARY KEY (tenant, name)
);

CREATE TABLE IF NOT EXISTS work_led_lines (
    tenant  INTEGER NOT NULL DEFAULT 1,
    entry   TEXT NOT NULL,
    account TEXT NOT NULL,
    debit   REAL NOT NULL DEFAULT 0,
    credit  REAL NOT NULL DEFAULT 0,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);
CREATE INDEX IF NOT EXISTS idx_work_led_lines_entry   ON work_led_lines(tenant, entry);
CREATE INDEX IF NOT EXISTS idx_work_led_lines_account ON work_led_lines(tenant, account);
CREATE INDEX IF NOT EXISTS idx_work_led_entries_status ON work_led_entries(tenant, docstatus, posting_date);

CREATE TABLE IF NOT EXISTS work_led_seq (
    tenant INTEGER NOT NULL,
    year   TEXT NOT NULL,
    n      INTEGER NOT NULL,
    PRIMARY KEY (tenant, year)
);

CREATE TABLE IF NOT EXISTS work_catalog_i18n (
    tenant  INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    ru      TEXT,
    en      TEXT,
    ko      TEXT,
    PRIMARY KEY (tenant, account)
);

CREATE TABLE IF NOT EXISTS work_money_accounts (
    tenant   INTEGER NOT NULL DEFAULT 1,
    account  TEXT NOT NULL,
    kind     TEXT,
    ord      INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'KRW',
    label    TEXT,
    PRIMARY KEY (tenant, account)
);

CREATE TABLE IF NOT EXISTS work_glossary (
    key  TEXT PRIMARY KEY,
    ru   TEXT,
    en   TEXT,
    ko   TEXT,
    kind TEXT DEFAULT 'ui',
    desc TEXT DEFAULT ''
);

-- Unified glossary: single source of truth for all apps.
CREATE TABLE IF NOT EXISTS avalone_glossary (
    key        TEXT PRIMARY KEY,
    ru         TEXT,
    en         TEXT,
    ko         TEXT,
    kind       TEXT DEFAULT 'ui',
    module     TEXT DEFAULT '',
    desc       TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_avalone_glossary_kind   ON avalone_glossary(kind);
CREATE INDEX IF NOT EXISTS idx_avalone_glossary_module ON avalone_glossary(module);

CREATE TABLE IF NOT EXISTS work_user_settings (
    tenant INTEGER NOT NULL DEFAULT 1,
    key    TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (tenant, key)
);

CREATE TABLE IF NOT EXISTS work_notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   INTEGER NOT NULL,
    type        TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    data        TEXT DEFAULT '',
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_work_notifications_tenant ON work_notifications(tenant_id, is_read, created_at);

CREATE TABLE IF NOT EXISTS work_trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   INTEGER NOT NULL,
    direction   TEXT NOT NULL CHECK(direction IN ('to_work','from_work')),
    trip_date   TEXT NOT NULL,
    trip_time   TEXT NOT NULL,
    comment     TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed','cancelled')),
    invite_code TEXT UNIQUE NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_work_trips_tenant ON work_trips(tenant_id, trip_date);

CREATE TABLE IF NOT EXISTS work_trip_members (
    trip_id     INTEGER NOT NULL REFERENCES work_trips(id) ON DELETE CASCADE,
    tenant_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK(role IN ('driver','passenger','not_going','unknown')),
    seats       INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (trip_id, tenant_id)
);

CREATE TABLE IF NOT EXISTS work_slept_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    account      TEXT,
    debit        TEXT,
    credit       TEXT,
    amount       REAL,
    posting_date TEXT,
    remark       TEXT,
    occurred_at  TEXT,
    PRIMARY KEY (tenant, name)
);
"""


def migrate() -> None:
    with connection() as con:
        _execute_script(con, SCHEMA)
    # Migrate legacy per-app glossaries into the unified table and seed portal keys.
    from avalone_core import glossary_db
    glossary_db.migrate()


def table_exists(name: str) -> bool:
    with connection() as con:
        r = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    return r is not None
