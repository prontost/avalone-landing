"""Backwards-compatible public API for the unified Avalone glossary.

New code should import from `avalone_core.glossary_db` directly.
This module re-exports the most common helpers so existing imports keep working.
"""

from avalone_core.glossary_db import (
    all_by_lang,
    apply_descriptions,
    audit,
    count,
    describe,
    entries,
    ensure_schema,
    get,
    i18n_js,
    missing_desc,
    migrate,
    migrate_legacy,
    seed_portal,
    set_desc,
    t,
    upsert,
    upsert_many,
)

__all__ = [
    "all_by_lang",
    "apply_descriptions",
    "audit",
    "count",
    "describe",
    "entries",
    "ensure_schema",
    "get",
    "i18n_js",
    "missing_desc",
    "migrate",
    "migrate_legacy",
    "seed_portal",
    "set_desc",
    "t",
    "upsert",
    "upsert_many",
]

# NOTE: the old in-memory `GLOSSARY` dict is gone. Use `t(key, lang)` or
# `all_by_lang()` instead. Template globals should register `t` and `i18n_js`
# from `avalone_core.glossary_db`.
