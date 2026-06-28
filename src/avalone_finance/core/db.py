"""Avalone Finance DB connector: uses the unified Avalone SQLite database.

All Avalone Finance tables live in the unified DB and use the `money_` prefix. Modules
continue importing `DB_PATH` from here; the actual connection comes from
`avalone_core.db`.
"""

from pathlib import Path

import avalone_core.db as _unified_db

DB_PATH: Path = _unified_db.DB_PATH
