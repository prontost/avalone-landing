"""Class-oriented glossary access for services and repositories.

This module wraps the functional `avalone_core.glossary_db` API in repository
and service classes so that new code can depend on a `GlossaryService`
instance instead of importing global functions.

The underlying `glossary_db` module remains the single source of truth for
schema, seeding, and backwards compatibility.
"""

from __future__ import annotations

from typing import Any

from avalone_core.database import Repository, Service
from avalone_core import glossary_db


class GlossaryRepository(Repository):
    """Repository for reading and writing glossary rows.

    Currently delegates to `glossary_db` because the glossary uses a single
    unified table and the functional API is stable. Future iterations can move
    SQL here if needed.
    """

    def t(self, key: str, lang: str = "ru") -> str:
        """Translate a key, falling back ru → en → key."""
        return glossary_db.get(key, lang)

    def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        return glossary_db.upsert_many(rows)

    def all_by_lang(self, kind: str | None = None, module: str | None = None) -> dict[str, dict[str, str]]:
        return glossary_db.all_by_lang(kind, module)

    def entries(self, kind: str | None = None, module: str | None = None) -> list[dict[str, Any]]:
        return glossary_db.entries(kind, module)

    def missing_desc(self, kind: str | None = None, module: str | None = None) -> list[str]:
        return glossary_db.missing_desc(kind, module)

    def set_desc(self, key: str, desc: str) -> None:
        glossary_db.set_desc(key, desc)

    def apply_descriptions(self) -> int:
        return glossary_db.apply_descriptions()

    def seed_portal(self) -> int:
        return glossary_db.seed_portal()

    def migrate(self) -> dict[str, Any]:
        return glossary_db.migrate()

    def audit(self) -> dict[str, Any]:
        return glossary_db.audit()


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

    def i18n(self, kind: str | None = None, module: str | None = None) -> dict[str, dict[str, str]]:
        return self._repo.all_by_lang(kind, module)

    def ensure_descriptions(self) -> int:
        return self._repo.apply_descriptions()

    def missing_descriptions(self, kind: str | None = None, module: str | None = None) -> list[str]:
        return self._repo.missing_desc(kind, module)
