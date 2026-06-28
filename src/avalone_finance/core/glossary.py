"""Avalone Finance-facing facade for the unified Avalone glossary.

The actual storage is `avalone_core.glossary_db` (table `avalone_glossary`).
This module keeps the old import path working for existing code.
"""

from avalone_core.glossary_db import (
    LANGS,
    all_by_lang,
    count,
    describe,
    entries,
    get,
    missing_desc,
    set_desc,
    t,
    upsert,
    upsert_many,
)

__all__ = [
    "LANGS",
    "all_by_lang",
    "count",
    "describe",
    "entries",
    "get",
    "missing_desc",
    "set_desc",
    "t",
    "upsert",
    "upsert_many",
]
