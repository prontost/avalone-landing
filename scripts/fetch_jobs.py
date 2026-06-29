#!/usr/bin/env python3
"""Fetch recent job postings from Koreabridge and store them in Avalone DB.

Usage:
    uv run python scripts/fetch_jobs.py [ru|en|ko]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from avalone_core.db import migrate
from avalone_landing.core.jobs.service import JobPostService


def main() -> int:
    migrate()
    result = JobPostService().fetch_and_store()
    print(f"Fetched and stored {result['fetched']} postings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
