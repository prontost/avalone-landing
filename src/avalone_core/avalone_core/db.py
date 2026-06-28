"""Unified SQLite database for the Avalone platform.

All platform data lives in a single file. Modules use prefixed tables:
- users, sessions
- money_accounts, money_led_entries, ...
- work_trips, work_trip_members, ...
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from avalone_core.database import Database

DEFAULT_DB_PATH = Path.home() / ".avalone" / "avalone.db"
DB_PATH: Path = DEFAULT_DB_PATH


def configure(path: str | Path | None = None) -> None:
    """Backward-compatible path configuration. Prefer `Database.configure()`."""
    global DB_PATH
    Database.configure(path)
    DB_PATH = Database.shared().path


def connection() -> sqlite3.Connection:
    """Backward-compatible connection factory. Prefer `Database.shared().connection()`."""
    return Database.shared().connection()


def _execute_script(con: sqlite3.Connection, sql: str) -> None:
    con.executescript(sql)
    con.commit()


SCHEMA = """
-- Users & sessions (single source of truth)
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    login          TEXT UNIQUE NOT NULL,
    pwhash         TEXT NOT NULL,
    name           TEXT DEFAULT '',
    email          TEXT DEFAULT '',
    email_verified INTEGER DEFAULT 0,
    verify_code    TEXT DEFAULT '',
    verify_sent    TEXT DEFAULT '',
    reset_token    TEXT DEFAULT '',
    reset_expires  TEXT DEFAULT '',
    language       TEXT DEFAULT 'auto',
    referral_code  TEXT UNIQUE,
    referred_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- RBAC roles and user assignments (replaces module-based admins)
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    permissions TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);

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

-- Work module has been removed; legacy work_* tables are dropped on migration.

-- Unified glossary is owned by GlossaryRepository (avalone_core.glossary_service).
-- Do NOT define the table here; the repository handles schema creation, column
-- migrations, and indexes after the core schema is applied.

-- Platform-wide server settings (SMTP, VAPID, etc.) managed by the admin panel.
CREATE TABLE IF NOT EXISTS avalone_global_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Device fingerprinting and screen-time tracking.
CREATE TABLE IF NOT EXISTS avalone_devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    device_id   TEXT UNIQUE,
    user_agent  TEXT,
    screen      TEXT,
    platform    TEXT,
    last_ip     TEXT,
    created_at  TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_avalone_devices_user ON avalone_devices(user_id);
CREATE INDEX IF NOT EXISTS idx_avalone_devices_fingerprint ON avalone_devices(fingerprint);
CREATE INDEX IF NOT EXISTS idx_avalone_devices_device_id ON avalone_devices(device_id);

CREATE TABLE IF NOT EXISTS avalone_screen_time (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    device_id   INTEGER NOT NULL REFERENCES avalone_devices(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    seconds     INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    UNIQUE(user_id, device_id, date)
);
CREATE INDEX IF NOT EXISTS idx_avalone_screen_time_user_date ON avalone_screen_time(user_id, date);

CREATE TABLE IF NOT EXISTS avalone_referrals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invitee_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_used         TEXT,
    device_fingerprint TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE(invitee_id)
);

CREATE TABLE IF NOT EXISTS avalone_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    source_page TEXT DEFAULT '',
    contact     TEXT DEFAULT '',
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_avalone_feedback_created ON avalone_feedback(created_at);
"""


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _apply_migrations() -> None:
    """Idempotently add Phase-2 columns/tables to an existing unified DB."""
    from avalone_core.database import Database

    with Database.shared().connection() as con:
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        except sqlite3.OperationalError:
            cols = set()
        additions = {
            "referral_code": "TEXT",
            "referred_by": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        }
        for col, dtype in additions.items():
            if col not in cols:
                try:
                    con.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                except sqlite3.OperationalError:
                    pass
        try:
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)"
            )
        except sqlite3.OperationalError:
            pass
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS avalone_devices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                fingerprint TEXT NOT NULL,
                device_id   TEXT UNIQUE,
                user_agent  TEXT,
                screen      TEXT,
                platform    TEXT,
                last_ip     TEXT,
                created_at  TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_avalone_devices_user ON avalone_devices(user_id);
            CREATE INDEX IF NOT EXISTS idx_avalone_devices_fingerprint ON avalone_devices(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_avalone_devices_device_id ON avalone_devices(device_id);

            CREATE TABLE IF NOT EXISTS avalone_screen_time (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                device_id   INTEGER NOT NULL REFERENCES avalone_devices(id) ON DELETE CASCADE,
                date        TEXT NOT NULL,
                seconds     INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL,
                UNIQUE(user_id, device_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_avalone_screen_time_user_date ON avalone_screen_time(user_id, date);

            CREATE TABLE IF NOT EXISTS avalone_referrals (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                invitee_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code_used         TEXT,
                device_fingerprint TEXT,
                created_at        TEXT NOT NULL,
                UNIQUE(invitee_id)
            );
            """
        )
        con.commit()


def _drop_work_tables() -> None:
    """Remove legacy Work module tables after the merge to a single app."""
    from avalone_core.database import Database

    legacy_tables = [
        "work_trip_members",
        "work_trips",
        "work_notifications",
        "work_user_settings",
        "work_user_apps",
        "work_slept_entries",
        "work_glossary",
        "work_money_accounts",
        "work_catalog_i18n",
        "work_led_lines",
        "work_led_entries",
        "work_led_accounts",
        "work_led_seq",
        "work_global_settings",
    ]
    with Database.shared().connection() as con:
        con.execute("PRAGMA foreign_keys=OFF")
        for table in legacy_tables:
            try:
                con.execute(f"DROP TABLE IF EXISTS {table}")
            except sqlite3.OperationalError:
                pass
        con.execute("PRAGMA foreign_keys=ON")
        con.commit()


def _migrate_admins_to_roles() -> None:
    """Convert legacy module-based admins table to RBAC roles."""
    from avalone_core.database import Database

    default_roles = {
        # Day-to-day finance features are available to every user by default.
        # Finance admin panel/settings stay limited to portal admins.
        "user": ["finance:read", "finance:write"],
        "admin": [
            "finance:read",
            "finance:write",
            "finance:admin",
            "users:manage",
            "server:settings",
        ],
        "owner": ["admin:full"],
    }
    mapping = {"portal": "admin", "money": "admin"}

    con = Database.shared().connection()
    try:
        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admins'"
        ).fetchone()
        if not table_exists:
            return

        for name, perms in default_roles.items():
            con.execute(
                "INSERT OR IGNORE INTO roles (name, permissions) VALUES (?, ?)",
                (name, json.dumps(perms, ensure_ascii=False)),
            )

        role_ids = {
            row["name"]: row["id"]
            for row in con.execute("SELECT id, name FROM roles WHERE name = ?",
                                   ("admin",))
        }

        rows = con.execute("SELECT user_id, module FROM admins").fetchall()
        for row in rows:
            role_name = mapping.get(row["module"])
            role_id = role_ids.get(role_name)
            if not role_id:
                continue
            con.execute(
                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
                (row["user_id"], role_id),
            )

        con.execute("PRAGMA foreign_keys=OFF")
        try:
            con.execute("DROP TABLE IF EXISTS admins")
        except sqlite3.OperationalError:
            pass
        con.execute("PRAGMA foreign_keys=ON")
        con.commit()
    finally:
        con.close()


def migrate() -> None:
    """Backward-compatible migration. Prefer `Database.shared().migrate()`."""
    Database.shared().migrate()
    _apply_migrations()
    _drop_work_tables()
    _migrate_admins_to_roles()


def table_exists(name: str) -> bool:
    """Backward-compatible helper. Prefer `Database.shared().table_exists()`."""
    return Database.shared().table_exists(name)
