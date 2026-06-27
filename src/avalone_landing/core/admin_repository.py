"""Cross-module data access for the Avalone platform admin panel."""

from __future__ import annotations

import sqlite3
from typing import Any

from avalone_core.database import Database, Repository


class AdminRepository(Repository):
    """Raw SQL access across portal users and module tables for admin operations."""

    # Module prefixes that contain tenant-isolated data.
    MODULE_PREFIXES = ("money_",)

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database.shared())

    def _conn(self) -> sqlite3.Connection:
        return self._db.connection()

    # ------------------------------------------------------------------
    # User listing
    # ------------------------------------------------------------------

    def list_users(self) -> list[sqlite3.Row]:
        with self._conn() as con:
            return con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users ORDER BY login"
            ).fetchall()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        with self._conn() as con:
            return con.execute(
                "SELECT id, login, email, email_verified, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    def user_exists(self, user_id: int) -> bool:
        with self._conn() as con:
            row = con.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        return bool(row)

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    def get_roles(self, user_id: int) -> list[str]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT module FROM admins WHERE user_id = ? ORDER BY module", (user_id,)
            ).fetchall()
        return [r["module"] for r in rows]

    def set_roles(self, user_id: int, roles: list[str]) -> None:
        """Replace the user's admin rows with the requested module roles."""
        with self._conn() as con:
            con.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            for module in roles:
                module = (module or "").strip().lower()
                if module:
                    con.execute(
                        "INSERT OR IGNORE INTO admins (user_id, module) VALUES (?, ?)",
                        (user_id, module),
                    )

    def is_admin_module(self, user_id: int, module: str) -> bool:
        with self._conn() as con:
            row = con.execute(
                "SELECT 1 FROM admins WHERE user_id = ? AND module = ?",
                (user_id, module),
            ).fetchone()
        return bool(row)

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def update_email(self, user_id: int, email: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET email = ?, email_verified = 0 WHERE id = ?",
                (email.strip().lower(), user_id),
            )

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    def set_reset_token(self, user_id: int, token: str, expires_at: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?",
                (token, expires_at, user_id),
            )

    def set_password_hash(self, user_id: int, pwhash: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET pwhash = ? WHERE id = ?",
                (pwhash, user_id),
            )

    def clear_reset_token(self, user_id: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE users SET reset_token = '', reset_expires = '' WHERE id = ?",
                (user_id,),
            )

    # ------------------------------------------------------------------
    # Module table introspection
    # ------------------------------------------------------------------

    def _module_tables(self) -> list[str]:
        """Return all existing tables with money_/work_ prefixes."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE ? OR name LIKE ?)",
                ("money_%", "work_%"),
            ).fetchall()
        return sorted({r["name"] for r in rows})

    def _tenant_column(self, table: str) -> str | None:
        """Return 'tenant' or 'tenant_id' if the table has one, else None."""
        info = self._table_info(table)
        names = {row["name"] for row in info}
        if "tenant" in names:
            return "tenant"
        if "tenant_id" in names:
            return "tenant_id"
        return None

    def _table_info(self, table: str) -> list[sqlite3.Row]:
        with self._conn() as con:
            return con.execute(f"PRAGMA table_info({table})").fetchall()

    def _pk_columns(self, table: str) -> list[str]:
        return [row["name"] for row in self._table_info(table) if row["pk"] > 0]

    def _columns(self, table: str) -> list[str]:
        return [row["name"] for row in self._table_info(table)]

    def _is_autoincrement_pk(self, table: str, columns: list[str] | None = None) -> bool:
        info = self._table_info(table)
        for row in info:
            if row["pk"] == 1:
                return bool(row["type"].upper() == "INTEGER")
        return False

    # ------------------------------------------------------------------
    # Counts per module
    # ------------------------------------------------------------------

    def module_counts(self, user_id: int) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in self._module_tables():
            tenant_col = self._tenant_column(table)
            if not tenant_col:
                continue
            with self._conn() as con:
                row = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {tenant_col} = ?", (user_id,)
                ).fetchone()
            counts[table] = row[0] if row else 0
        return counts

    # ------------------------------------------------------------------
    # Wipe / export / transfer / copy
    # ------------------------------------------------------------------

    def wipe_user_data(self, user_id: int) -> dict[str, int]:
        """Delete all module rows for user_id. Returns deleted counts per table."""
        deleted: dict[str, int] = {}
        with self._conn() as con:
            for table in self._module_tables():
                tenant_col = self._tenant_column(table)
                if not tenant_col:
                    continue
                cur = con.execute(
                    f"DELETE FROM {table} WHERE {tenant_col} = ?", (user_id,)
                )
                deleted[table] = cur.rowcount
            con.commit()
        return deleted

    def export_user_data(self, user_id: int) -> dict[str, Any]:
        """Return a JSON-serializable dump of all module rows for user_id."""
        data: dict[str, Any] = {"money": {}}
        for table in self._module_tables():
            prefix = table.split("_")[0]
            tenant_col = self._tenant_column(table)
            if not tenant_col or prefix != "money":
                continue
            with self._conn() as con:
                rows = con.execute(
                    f"SELECT * FROM {table} WHERE {tenant_col} = ?", (user_id,)
                ).fetchall()
            data[prefix][table] = [dict(r) for r in rows]
        return data

    def transfer_user_data(self, from_user_id: int, to_user_id: int) -> dict[str, int]:
        """Update tenant/tenant_id from from_user_id to to_user_id across module tables."""
        updated: dict[str, int] = {}
        with self._conn() as con:
            for table in self._module_tables():
                tenant_col = self._tenant_column(table)
                if not tenant_col:
                    continue
                cur = con.execute(
                    f"UPDATE {table} SET {tenant_col} = ? WHERE {tenant_col} = ?",
                    (to_user_id, from_user_id),
                )
                updated[table] = cur.rowcount
            con.commit()
        return updated

    def copy_tables(self, from_user_id: int, to_user_id: int, tables: list[str]) -> dict[str, int]:
        """Copy rows from selected module tables to a new tenant."""
        copied: dict[str, int] = {}
        with self._conn() as con:
            for table in tables:
                tenant_col = self._tenant_column(table)
                if not tenant_col:
                    continue
                columns = self._columns(table)
                if not columns:
                    continue

                # For tables with a single INTEGER PRIMARY KEY (autoincrement), skip the id column
                # so SQLite generates new ids and we avoid PK conflicts.
                skip_id = self._is_autoincrement_pk(table)
                if skip_id:
                    pk_col = self._pk_columns(table)[0]
                    insert_cols = [c for c in columns if c != pk_col]
                else:
                    insert_cols = columns

                select_cols: list[str] = []
                for c in insert_cols:
                    if c == tenant_col:
                        select_cols.append("?")
                    else:
                        select_cols.append(c)

                sql = (
                    f"INSERT OR IGNORE INTO {table} ({', '.join(insert_cols)}) "
                    f"SELECT {', '.join(select_cols)} FROM {table} WHERE {tenant_col} = ?"
                )
                cur = con.execute(sql, (to_user_id, from_user_id))
                copied[table] = cur.rowcount
            con.commit()
        return copied

    # ------------------------------------------------------------------
    # Server settings
    # ------------------------------------------------------------------

    def list_server_settings(self) -> dict[str, str]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT key, value FROM avalone_global_settings"
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_server_settings(self, settings: dict[str, str]) -> None:
        with self._conn() as con:
            for key, value in settings.items():
                con.execute(
                    "INSERT INTO avalone_global_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            con.commit()

    # ------------------------------------------------------------------
    # Dashboard counts
    # ------------------------------------------------------------------

    def count_users(self) -> int:
        with self._conn() as con:
            row = con.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0

    def count_admins(self) -> int:
        with self._conn() as con:
            row = con.execute("SELECT COUNT(DISTINCT user_id) FROM admins").fetchone()
        return row[0] if row else 0
