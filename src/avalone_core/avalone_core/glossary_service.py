"""Class-oriented glossary access for services and repositories.

This module owns the glossary repository and service. `avalone_core.glossary_db`
remains a backward-compatible facade over `GlossaryRepository`.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from avalone_core.database import Repository, Service
from avalone_core.db import connection
from avalone_core.glossary_db import (
    LANGS,
    _PORTAL_SEED,
    _PORTAL_SEED_EXTRA,
    _now,
)

_TABLE_SQL = """
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
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_avalone_glossary_kind   ON avalone_glossary(kind);
CREATE INDEX IF NOT EXISTS idx_avalone_glossary_module ON avalone_glossary(module);
"""

# Kept for consumers that may import it by name; do not use directly for executescript.
SCHEMA = _TABLE_SQL + _INDEX_SQL


class GlossaryRepository(Repository):
    """Repository for reading and writing glossary rows."""

    def ensure_schema(self) -> None:
        # Create the table first (no-op if it already exists). If an existing
        # table is missing columns added in later iterations, add them before
        # creating indexes, otherwise index creation on missing columns fails.
        with connection() as con:
            con.executescript(_TABLE_SQL)
        self._ensure_columns()
        with connection() as con:
            con.executescript(_INDEX_SQL)

    def _ensure_columns(self) -> None:
        """Add columns introduced after the initial schema without recreating table."""
        columns = {
            "kind": "TEXT DEFAULT 'ui'",
            "module": "TEXT DEFAULT ''",
            "desc": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        }
        with connection() as con:
            existing = {row[1] for row in con.execute("PRAGMA table_info(avalone_glossary)").fetchall()}
            for name, dtype in columns.items():
                if name not in existing:
                    try:
                        con.execute(f"ALTER TABLE avalone_glossary ADD COLUMN {name} {dtype}")
                    except sqlite3.OperationalError:
                        pass
            con.commit()

    def upsert(
        self,
        key: str,
        ru: str = "",
        en: str = "",
        ko: str = "",
        kind: str = "ui",
        module: str = "",
        desc: str | None = None,
    ) -> None:
        self.upsert_many(
            [
                {
                    "key": key,
                    "ru": ru,
                    "en": en,
                    "ko": ko,
                    "kind": kind,
                    "module": module,
                    "desc": desc,
                }
            ]
        )

    def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        """Insert or update rows. desc=None means "do not overwrite existing desc".
        desc="" explicitly clears it. Returns number of processed rows."""
        with connection() as con:
            for r in rows:
                desc = r.get("desc")
                now = _now()
                params = (
                    r["key"],
                    r.get("ru", ""),
                    r.get("en", ""),
                    r.get("ko", ""),
                    r.get("kind", "ui"),
                    r.get("module", ""),
                    desc if desc is not None else "",
                    now,
                )
                if desc is None:
                    con.execute(
                        "INSERT INTO avalone_glossary "
                        "(key, ru, en, ko, kind, module, desc, updated_at) VALUES (?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET "
                        "ru=COALESCE(NULLIF(excluded.ru,''),avalone_glossary.ru), "
                        "en=COALESCE(NULLIF(excluded.en,''),avalone_glossary.en), "
                        "ko=COALESCE(NULLIF(excluded.ko,''),avalone_glossary.ko), "
                        "kind=COALESCE(NULLIF(excluded.kind,''),avalone_glossary.kind), "
                        "module=COALESCE(NULLIF(excluded.module,''),avalone_glossary.module), "
                        "updated_at=excluded.updated_at "
                        "WHERE excluded.ru<>avalone_glossary.ru OR excluded.en<>avalone_glossary.en "
                        "OR excluded.ko<>avalone_glossary.ko OR excluded.kind<>avalone_glossary.kind "
                        "OR excluded.module<>avalone_glossary.module",
                        params,
                    )
                else:
                    con.execute(
                        "INSERT INTO avalone_glossary "
                        "(key, ru, en, ko, kind, module, desc, updated_at) VALUES (?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET "
                        "ru=COALESCE(NULLIF(excluded.ru,''),avalone_glossary.ru), "
                        "en=COALESCE(NULLIF(excluded.en,''),avalone_glossary.en), "
                        "ko=COALESCE(NULLIF(excluded.ko,''),avalone_glossary.ko), "
                        "kind=COALESCE(NULLIF(excluded.kind,''),avalone_glossary.kind), "
                        "module=COALESCE(NULLIF(excluded.module,''),avalone_glossary.module), "
                        "desc=excluded.desc, updated_at=excluded.updated_at",
                        params,
                    )
        return len(rows)

    def set_desc(self, key: str, desc: str) -> None:
        with connection() as con:
            con.execute(
                "UPDATE avalone_glossary SET desc=?, updated_at=? WHERE key=?",
                (desc, _now(), key),
            )

    def touch(self, key: str) -> None:
        with connection() as con:
            con.execute(
                "UPDATE avalone_glossary SET updated_at=? WHERE key=?",
                (_now(), key),
            )

    def get(self, key: str, lang: str = "ru") -> str:
        """Translate key; fallback ru -> en -> key."""
        with connection() as con:
            row = con.execute(
                "SELECT ru, en, ko FROM avalone_glossary WHERE key=?", (key,)
            ).fetchone()
        if not row:
            return key
        vals = {"ru": row["ru"], "en": row["en"], "ko": row["ko"]}
        return vals.get(lang) or vals["ru"] or vals["en"] or key

    def t(self, key: str, lang: str = "ru") -> str:
        """Translate a key, falling back ru → en → key."""
        return self.get(key, lang)

    def all_by_lang(
        self, kind: str | None = None, module: str | None = None
    ) -> dict[str, dict[str, str]]:
        """{lang: {key: text}} convenient for front-end bootstrapping."""
        out: dict[str, dict[str, str]] = {l: {} for l in LANGS}
        where: list[str] = []
        params: list[Any] = []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if module:
            where.append("module=?")
            params.append(module)
        sql = "SELECT key, ru, en, ko FROM avalone_glossary"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with connection() as con:
            for row in con.execute(sql, params):
                vals = {"ru": row["ru"], "en": row["en"], "ko": row["ko"]}
                for l in LANGS:
                    if vals.get(l):
                        out[l][row["key"]] = vals[l]
        return out

    def i18n_js(self) -> dict[str, dict[str, str]]:
        """Backwards-compatible alias for Jinja global."""
        return self.all_by_lang()

    def entries(
        self, kind: str | None = None, module: str | None = None
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if module:
            where.append("module=?")
            params.append(module)
        sql = "SELECT key, ru, en, ko, kind, module, desc FROM avalone_glossary"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY module, kind, key"
        with connection() as con:
            rows = con.execute(sql, params).fetchall()
        return [
            {
                "key": r["key"],
                "ru": r["ru"] or "",
                "en": r["en"] or "",
                "ko": r["ko"] or "",
                "kind": r["kind"] or "ui",
                "module": r["module"] or "",
                "desc": r["desc"] or "",
            }
            for r in rows
        ]

    def describe(self, key: str) -> str:
        with connection() as con:
            row = con.execute(
                "SELECT desc FROM avalone_glossary WHERE key=?", (key,)
            ).fetchone()
        return row["desc"] if row and row["desc"] else ""

    def missing_desc(
        self, kind: str | None = None, module: str | None = None
    ) -> list[str]:
        where = ["(desc IS NULL OR desc='')"]
        params: list[Any] = []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if module:
            where.append("module=?")
            params.append(module)
        sql = (
            "SELECT key FROM avalone_glossary WHERE "
            + " AND ".join(where)
            + " ORDER BY module, kind, key"
        )
        with connection() as con:
            return [r["key"] for r in con.execute(sql, params)]

    def count(self, kind: str | None = None, module: str | None = None) -> int:
        where: list[str] = []
        params: list[Any] = []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if module:
            where.append("module=?")
            params.append(module)
        sql = "SELECT COUNT(*) FROM avalone_glossary"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with connection() as con:
            return con.execute(sql, params).fetchone()[0]

    def _legacy_table_exists(self, con: sqlite3.Connection, name: str) -> bool:
        r = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return r is not None

    def _merge_legacy(
        self, con: sqlite3.Connection, table: str, module: str
    ) -> int:
        """Copy rows from a legacy per-app glossary table into avalone_glossary,
        merging translations and descriptions without overwriting non-empty values."""
        if not self._legacy_table_exists(con, table):
            return 0
        rows = con.execute(f"SELECT key, ru, en, ko, kind, desc FROM {table}").fetchall()
        merged = 0
        for r in rows:
            key, ru, en, ko, kind, desc = r
            existing = con.execute(
                "SELECT ru, en, ko, desc FROM avalone_glossary WHERE key=?", (key,)
            ).fetchone()
            if existing:
                eru, een, eko, edesc = existing
                ru = ru or eru or ""
                en = en or een or ""
                ko = ko or eko or ""
                desc = desc or edesc or ""
                con.execute(
                    "UPDATE avalone_glossary SET ru=?, en=?, ko=?, kind=COALESCE(NULLIF(?,''),kind), "
                    "module=COALESCE(NULLIF(?,''),module), desc=? WHERE key=?",
                    (ru, en, ko, kind, module, desc, key),
                )
            else:
                con.execute(
                    "INSERT INTO avalone_glossary (key, ru, en, ko, kind, module, desc, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        key,
                        ru or "",
                        en or "",
                        ko or "",
                        kind or "ui",
                        module,
                        desc or "",
                        _now(),
                    ),
                )
            merged += 1
        return merged

    def migrate_legacy(self) -> dict[str, int]:
        """Migrate money_glossary into avalone_glossary.
        Safe to call multiple times; idempotent merge."""
        with connection() as con:
            n_money = self._merge_legacy(con, "money_glossary", "money")
        return {"money": n_money}

    def seed_portal(self) -> int:
        """Seed portal/shared keys. Idempotent: preserves existing desc if already set."""
        from avalone_core.ui_glossary import describe as ui_describe

        rows = []
        for row in _PORTAL_SEED + _PORTAL_SEED_EXTRA:
            d = dict(row)
            d.setdefault("desc", ui_describe(row["key"]))
            rows.append(d)
        return self.upsert_many(rows)

    def apply_descriptions(self) -> int:
        """Fill empty desc values for UI keys using ui_glossary rules."""
        from avalone_core.ui_glossary import describe as ui_describe

        updated = 0
        with connection() as con:
            keys = [
                r["key"]
                for r in con.execute(
                    "SELECT key FROM avalone_glossary WHERE (desc IS NULL OR desc='')"
                )
            ]
        for key in keys:
            d = ui_describe(key)
            if d:
                self.set_desc(key, d)
                updated += 1
        return updated

    def migrate(self) -> dict[str, Any]:
        """Run schema creation, legacy migration, portal seed, and description backfill.
        Called from avalone_core.db.migrate() on every app startup."""
        self.ensure_schema()
        legacy = self.migrate_legacy()
        portal = self.seed_portal()
        described = self.apply_descriptions()
        return {"legacy": legacy, "portal": portal, "described": described}

    def audit(self) -> dict[str, Any]:
        """Human-readable summary for CLI/debugging."""
        return {
            "total": self.count(),
            "missing_desc": self.missing_desc(),
            "by_module": {
                module: self.count(module=module)
                for module in ("portal", "money")
            },
        }


class GlossaryService(Service):
    """Service facade for glossary operations.

    Business code should receive this service via constructor injection and
    call `translate()` for user-facing strings.
    """

    def __init__(self, repository: GlossaryRepository | None = None) -> None:
        self._repo = repository or GlossaryRepository()

    def translate(self, key: str, lang: str = "ru") -> str:
        return self._repo.t(key, lang)

    def seed(self, rows: list[dict[str, Any]]) -> int:
        return self._repo.upsert_many(rows)

    def i18n(
        self, kind: str | None = None, module: str | None = None
    ) -> dict[str, dict[str, str]]:
        return self._repo.all_by_lang(kind, module)

    def ensure_descriptions(self) -> int:
        return self._repo.apply_descriptions()

    def missing_descriptions(
        self, kind: str | None = None, module: str | None = None
    ) -> list[str]:
        return self._repo.missing_desc(kind, module)
