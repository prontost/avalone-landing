"""Test-wide setup for avalone.online."""

from __future__ import annotations

import os
import tempfile

os.environ["AVALONE_DB_PATH"] = tempfile.mktemp(suffix=".db")

from avalone_core.db import migrate as _migrate_db

_migrate_db()

# Seed finance glossary so engine error messages are translated in unit tests.
from avalone_finance.core.glossary_seed import seed as _seed_finance_glossary
_seed_finance_glossary()
