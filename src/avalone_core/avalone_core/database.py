"""Shared database infrastructure for the Avalone platform.

Provides a single `Database` class that owns the SQLite connection lifecycle
and migration. Repositories and services receive a `Database` instance via
constructor injection instead of importing global connection helpers.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

DEFAULT_DB_PATH = Path.home() / ".avalone" / "avalone.db"


class ClosingConnection(sqlite3.Connection):
    """A ``sqlite3.Connection`` that closes itself when used as a context manager.

    The standard library connection only commits/rolls back on ``__exit__``;
    it leaks the underlying file descriptor.  This subclass closes the
    connection, matching the behaviour users of ``Database.connection()`` expect.
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__(str(path), check_same_thread=False)
        self.row_factory = sqlite3.Row
        self.execute("PRAGMA foreign_keys = ON")

    def __enter__(self) -> sqlite3.Connection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Commit or rollback the active transaction before closing, otherwise
        # pending changes are silently discarded by sqlite3.Connection.close().
        super().__exit__(exc_type, exc_val, exc_tb)
        self.close()


class Database:
    """Owner of the unified Avalone SQLite database.

    The path can be overridden once per process via `configure()` or the
    `AVALONE_DB_PATH` environment variable. Repositories should accept a
    `Database` instance and call `db.connection()` when they need to execute
    SQL.
    """

    _instance: Database | None = None

    def __init__(self, path: str | Path | None = None) -> None:
        if path:
            self._path = Path(path)
        elif os.environ.get("AVALONE_DB_PATH"):
            self._path = Path(os.environ["AVALONE_DB_PATH"])
        else:
            self._path = DEFAULT_DB_PATH

    @classmethod
    def shared(cls) -> Database:
        """Return the process-wide shared database instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def configure(cls, path: str | Path | None = None) -> None:
        """Reconfigure the shared instance path. Existing connections are not
        affected, but all future calls to `shared()` will use the new path."""
        cls._instance = cls(path)

    @property
    def path(self) -> Path:
        return self._path

    def connection(self) -> sqlite3.Connection:
        """Open a new connection with the platform defaults.

        The returned connection is a ``ClosingConnection`` — it closes itself
        when used as a context manager, preventing file-descriptor leaks.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return ClosingConnection(self._path)

    def table_exists(self, name: str) -> bool:
        with self.connection() as con:
            row = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
        return row is not None

    def migrate(self) -> None:
        """Create or update the unified schema and run glossary migration."""
        from avalone_core.db import SCHEMA

        with self.connection() as con:
            con.executescript(SCHEMA)
            con.commit()

        self._ensure_user_name_column()

        from avalone_core import glossary_db

        glossary_db.migrate()

    def _ensure_user_name_column(self) -> None:
        with self.connection() as con:
            cols = [row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()]
            if "name" not in cols:
                con.execute("ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''")
                con.commit()

    def __enter__(self) -> sqlite3.Connection:
        self._conn = self.connection()
        return self._conn

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]


class Repository:
    """Base class for all repositories.

    Subclasses receive a `Database` instance and keep SQL inside the repository
    boundary.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or Database.shared()


class Service:
    """Base class for all services.

    Subclasses receive repositories and other services via constructor
    injection.
    """

    def __init__(self) -> None:
        pass
