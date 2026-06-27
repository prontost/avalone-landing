"""Backward-compatible re-export of the shared Avalone glossary."""

from avalone_core.glossary_db import all_by_lang, i18n_js, t

__all__ = ["all_by_lang", "i18n_js", "t"]
