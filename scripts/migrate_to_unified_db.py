"""Migrate three separate SQLite DBs into one unified Avalone DB.

Source:
  ~/.avalone/avalone.db   -> users
  ~/.finance/finance.db     -> money_* module
  ~/.work/work.db       -> work_* module

Target:
  ~/.avalone/avalone.db (modified in place after backup)

Tenant remapping:
  Avalone user lucifer currently has id=1.
  Avalone Finance tenant 3 and Work tenant 3 belong to lucifer.
  After migration tenant_id == user_id == 1.
"""

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from avalone_core.db import configure, connection, migrate

HOME = Path.home()
AVALONE_DB = HOME / ".avalone" / "avalone.db"
COUNTA_DB = HOME / ".finance" / "finance.db"
WORK_DB = HOME / ".work" / "work.db"
BACKUP_DIR = HOME / ".avalone" / "backups"

# Tenant remapping: old module tenant_id -> new unified user_id.
# Determined from external_users tables: avalone user id 1 -> tenant 3 in both modules.
TENANT_MAP = {3: 1}
NEW_TENANT = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_table(
    dst_con: sqlite3.Connection,
    src_path: Path,
    src_table: str,
    dst_table: str,
    tenant_map: dict[int, int] | None = None,
) -> None:
    print(f"  copying {src_path.name}.{src_table} -> {dst_table}")
    with sqlite3.connect(str(src_path)) as src_con:
        src_con.row_factory = sqlite3.Row
        cols = [desc[1] for desc in src_con.execute(f"PRAGMA table_info({src_table})")]
        if not cols:
            return
        tenant_col = None
        if tenant_map:
            if "tenant" in cols:
                tenant_col = "tenant"
            elif "tenant_id" in cols:
                tenant_col = "tenant_id"
        if tenant_col:
            placeholders_t = ",".join(["?"] * len(tenant_map))
            rows = src_con.execute(
                f"SELECT * FROM {src_table} WHERE {tenant_col} IN ({placeholders_t})",
                list(tenant_map.keys()),
            ).fetchall()
        else:
            rows = src_con.execute(f"SELECT * FROM {src_table}").fetchall()
        if not rows:
            return
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        tenant_col = None
        if tenant_map:
            if "tenant" in cols:
                tenant_col = "tenant"
            elif "tenant_id" in cols:
                tenant_col = "tenant_id"
        if tenant_col:
            tenant_idx = cols.index(tenant_col)
            mapped = []
            for row in rows:
                row = list(row)
                old_tenant = row[tenant_idx]
                row[tenant_idx] = tenant_map.get(old_tenant, old_tenant)
                mapped.append(tuple(row))
            rows = mapped
        dst_con.execute(f"DELETE FROM {dst_table}")
        dst_con.executemany(f"INSERT INTO {dst_table} ({col_names}) VALUES ({placeholders})", rows)


def _attach_and_copy(
    con: sqlite3.Connection,
    source_path: Path,
    alias: str,
    table_mapping: dict[str, str],
    tenant_map: dict[int, int] | None = None,
) -> None:
    for src_table, dst_table in table_mapping.items():
        _copy_table(con, source_path, src_table, dst_table, tenant_map)


def _ensure_user_columns(con: sqlite3.Connection) -> None:
    """Add columns that Avalone source may lack but Avalone Finance/Work need."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(users)")}
    for col, dtype in (
        ("email_verified", "INTEGER DEFAULT 0"),
        ("verify_code", "TEXT DEFAULT ''"),
        ("verify_sent", "TEXT DEFAULT ''"),
        ("reset_token", "TEXT DEFAULT ''"),
        ("reset_expires", "TEXT DEFAULT ''"),
    ):
        if col not in existing:
            con.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")


def _copy_users(con: sqlite3.Connection) -> None:
    print("copying users from Avalone DB")
    with sqlite3.connect(str(AVALONE_DB)) as src_con:
        src_con.row_factory = sqlite3.Row
        src_users = src_con.execute("SELECT * FROM users").fetchall()
        cols = [desc[1] for desc in src_con.execute("PRAGMA table_info(users)")]
    placeholders = ",".join(["?"] * len(cols))
    col_names = ",".join(cols)
    con.execute("DELETE FROM users")
    con.executemany(f"INSERT INTO users ({col_names}) VALUES ({placeholders})", src_users)


def _migrate_finance(con: sqlite3.Connection) -> None:
    print("migrating Avalone Finance module")
    table_mapping = {
        "global_settings": "money_global_settings",
        "led_accounts": "money_led_accounts",
        "led_entries": "money_led_entries",
        "led_lines": "money_led_lines",
        "led_seq": "money_led_seq",
        "catalog_i18n": "money_catalog_i18n",
        "money_accounts": "money_money_accounts",
        "glossary": "money_glossary",
        "user_settings": "money_user_settings",
        "notifications": "money_notifications",
        "entry_meta": "money_entry_meta",
        "slept_entries": "money_slept_entries",
    }
    _attach_and_copy(con, COUNTA_DB, "finance", table_mapping, TENANT_MAP)


def _migrate_work_trips(con: sqlite3.Connection) -> None:
    print("  migrating work trips with tenant_id remap")
    with sqlite3.connect(str(WORK_DB)) as src_con:
        src_con.row_factory = sqlite3.Row
        trips = src_con.execute("SELECT * FROM trips WHERE tenant_id = ?", (3,)).fetchall()
        trip_cols = [desc[1] for desc in src_con.execute("PRAGMA table_info(trips)")]
        if trips:
            placeholders = ",".join(["?"] * len(trip_cols))
            col_names = ",".join(trip_cols)
            tenant_idx = trip_cols.index("tenant_id")
            mapped = []
            for row in trips:
                row = list(row)
                row[tenant_idx] = TENANT_MAP.get(row[tenant_idx], row[tenant_idx])
                mapped.append(tuple(row))
            con.execute("DELETE FROM work_trips")
            con.executemany(f"INSERT INTO work_trips ({col_names}) VALUES ({placeholders})", mapped)

        members = src_con.execute("SELECT * FROM trip_members WHERE tenant_id = ?", (3,)).fetchall()
        member_cols = [desc[1] for desc in src_con.execute("PRAGMA table_info(trip_members)")]
        if members:
            placeholders = ",".join(["?"] * len(member_cols))
            col_names = ",".join(member_cols)
            tenant_idx = member_cols.index("tenant_id")
            mapped = []
            for row in members:
                row = list(row)
                row[tenant_idx] = TENANT_MAP.get(row[tenant_idx], row[tenant_idx])
                mapped.append(tuple(row))
            con.execute("DELETE FROM work_trip_members")
            con.executemany(f"INSERT INTO work_trip_members ({col_names}) VALUES ({placeholders})", mapped)


def _migrate_work(con: sqlite3.Connection) -> None:
    print("migrating Work module")
    table_mapping = {
        "global_settings": "work_global_settings",
        "led_accounts": "work_led_accounts",
        "led_entries": "work_led_entries",
        "led_lines": "work_led_lines",
        "led_seq": "work_led_seq",
        "catalog_i18n": "work_catalog_i18n",
        "money_accounts": "work_money_accounts",
        "glossary": "work_glossary",
        "user_settings": "work_user_settings",
        "notifications": "work_notifications",
        "entry_meta": "work_entry_meta",
        "slept_entries": "work_slept_entries",
    }
    _attach_and_copy(con, WORK_DB, "work", table_mapping, TENANT_MAP)
    _migrate_work_trips(con)


def _fix_sequences(con: sqlite3.Connection) -> None:
    # Re-sequence AUTOINCREMENT tables after manual inserts.
    for table in ["work_trips", "work_trip_members", "money_notifications", "work_notifications"]:
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone():
            continue
        cols = [desc[1] for desc in con.execute(f"PRAGMA table_info({table})")]
        if "id" not in cols:
            continue
        max_id = con.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0]
        con.execute(
            "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (?, ?)",
            (table, max_id),
        )


def _make_lucifer_admin(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM admins")
    lucifer = con.execute("SELECT id FROM users WHERE login='lucifer'").fetchone()
    if lucifer:
        con.execute("INSERT OR IGNORE INTO admins (user_id, module) VALUES (?, 'money')", (lucifer[0],))
        con.execute("INSERT OR IGNORE INTO admins (user_id, module) VALUES (?, 'work')", (lucifer[0],))


def _verify_emails(con: sqlite3.Connection) -> None:
    con.execute("UPDATE users SET email_verified = 1 WHERE email != ''")


def _fix_finance_glossary(con: sqlite3.Connection) -> None:
    """Update Avalone Finance UI glossary keys that changed after unified platform migration."""
    updates = {
        "tab_more": "⚙️ Настройки",
        "tab_bal": "💰",
        "tab_bal_t": "Баланс",
        "tab_entry_t": "Главная",
        "sec_account": "👤 Аккаунт",
        "acc_managed_in_avalone": "Управляется в профиле Avalone",
        "open_profile": "Открыть профиль",
    }
    for key, ru in updates.items():
        con.execute(
            "INSERT INTO money_glossary (key, ru, kind) VALUES (?, ?, 'ui') "
            "ON CONFLICT(key) DO UPDATE SET ru=excluded.ru",
            (key, ru),
        )


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for src in (AVALONE_DB, COUNTA_DB, WORK_DB):
        if src.exists():
            shutil.copy(src, BACKUP_DIR / f"{src.stem}-{ts}.db")

    configure(AVALONE_DB)
    print("creating unified schema")
    migrate()

    with connection() as con:
        _copy_users(con)
        _ensure_user_columns(con)
        _migrate_finance(con)
        _migrate_work(con)
        _fix_sequences(con)
        _make_lucifer_admin(con)
        _verify_emails(con)
        _fix_finance_glossary(con)
        con.commit()

    print("migration complete")
    print(f"unified DB: {AVALONE_DB}")


if __name__ == "__main__":
    main()
