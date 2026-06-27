"""Feature-level RBAC roles and permissions for the Avalone platform.

Roles are stored in the `roles` table; user assignments live in `user_roles`.
The special `admin:full` permission grants every other permission automatically.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from avalone_core.database import Database, Repository, Service


_DEFAULT_ROLES: dict[str, list[str]] = {
    "user": ["finance:read"],
    "finance_manager": ["finance:read", "finance:write", "finance:admin"],
    "admin": [
        "finance:read",
        "finance:write",
        "finance:admin",
        "users:manage",
        "server:settings",
    ],
    "owner": ["admin:full"],
}

_ALL_PERMISSIONS: set[str] = set().union(*_DEFAULT_ROLES.values()) - {"admin:full"}


class RoleRepository(Repository):
    """SQL access for the RBAC `roles` and `user_roles` tables."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database.shared())

    def _conn(self) -> sqlite3.Connection:
        return self._db.connection()

    def _ensure_schema(self) -> None:
        """Create roles tables if they do not exist yet."""
        with self._conn() as con:
            con.executescript(
                """
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
                """
            )

    def ensure_defaults(self) -> None:
        """Insert the default roles if they are missing."""
        self._ensure_schema()
        with self._conn() as con:
            for name, perms in _DEFAULT_ROLES.items():
                con.execute(
                    "INSERT OR IGNORE INTO roles (name, permissions) VALUES (?, ?)",
                    (name, json.dumps(perms, ensure_ascii=False)),
                )

    def list_roles(self) -> list[dict[str, Any]]:
        self.ensure_defaults()
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, name, permissions FROM roles ORDER BY id"
            ).fetchall()
        return [
            {"id": r["id"], "name": r["name"], "permissions": json.loads(r["permissions"])}
            for r in rows
        ]

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        self.ensure_defaults()
        with self._conn() as con:
            row = con.execute(
                "SELECT id, name, permissions FROM roles WHERE name = ?", (name,)
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "permissions": json.loads(row["permissions"]),
        }

    def get_role_names_for_user(self, user_id: int) -> list[str]:
        self.ensure_defaults()
        with self._conn() as con:
            rows = con.execute(
                "SELECT r.name FROM roles r "
                "JOIN user_roles ur ON ur.role_id = r.id "
                "WHERE ur.user_id = ? ORDER BY r.name",
                (user_id,),
            ).fetchall()
        return [r["name"] for r in rows]

    def get_permissions_for_user(self, user_id: int) -> set[str]:
        self.ensure_defaults()
        with self._conn() as con:
            rows = con.execute(
                "SELECT r.permissions FROM roles r "
                "JOIN user_roles ur ON ur.role_id = r.id "
                "WHERE ur.user_id = ?",
                (user_id,),
            ).fetchall()
        perms: set[str] = set()
        for row in rows:
            perms.update(json.loads(row["permissions"]))
        return perms

    def set_user_roles(self, user_id: int, role_names: list[str]) -> None:
        """Replace the user's assigned roles with the requested list."""
        self.ensure_defaults()
        names = {name.strip().lower() for name in role_names if name and name.strip()}
        with self._conn() as con:
            con.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            if names:
                con.executemany(
                    "INSERT INTO user_roles (user_id, role_id) "
                    "SELECT ?, id FROM roles WHERE name = ?",
                    [(user_id, name) for name in names],
                )


class RoleService(Service):
    """Business logic for feature-level RBAC checks."""

    def __init__(self, repo: RoleRepository | None = None) -> None:
        self._repo = repo or RoleRepository()

    def ensure_defaults(self) -> None:
        self._repo.ensure_defaults()

    def permissions_for(self, user_id: int) -> set[str]:
        self.ensure_defaults()
        return self._repo.get_permissions_for_user(user_id)

    def has_permission(self, user_id: int | None, permission: str) -> bool:
        if not user_id:
            return False
        perms = self.permissions_for(user_id)
        if "admin:full" in perms:
            return True
        return permission in perms

    def has_any_permission(self, user_id: int | None, permissions: set[str]) -> bool:
        if not user_id:
            return False
        perms = self.permissions_for(user_id)
        if "admin:full" in perms:
            return True
        return not permissions.isdisjoint(perms)

    def roles_for(self, user_id: int) -> list[str]:
        self.ensure_defaults()
        return self._repo.get_role_names_for_user(user_id)

    def assign_roles(self, user_id: int, role_names: list[str]) -> None:
        self.ensure_defaults()
        self._repo.set_user_roles(user_id, role_names)
