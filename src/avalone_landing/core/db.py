"""Database path for Avalone identity."""

import os
from pathlib import Path

_DB_DIR = Path(os.environ.get("AVALONE_DATA_DIR", Path.home() / ".avalone"))
DB_PATH = _DB_DIR / "avalone.db"
