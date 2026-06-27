"""Glossary health check.

Verifies that the unified glossary has no keys without a meta-context
description. Run with the Avalone Python path set to src/avalone_core, e.g.:

    PYTHONPATH=src/avalone_core python3 scripts/check_glossary.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC_CORE = ROOT / "src" / "avalone_core"

if str(SRC_CORE) not in sys.path:
    sys.path.insert(0, str(SRC_CORE))

from avalone_core.db import migrate
from avalone_core import glossary_db


def main() -> int:
    migrate()
    total = glossary_db.count()
    missing = glossary_db.missing_desc()
    by_module = {
        module: glossary_db.count(module=module)
        for module in ("portal", "money", "work")
    }
    by_kind = {
        kind: glossary_db.count(kind=kind)
        for kind in ("ui", "category", "currency", "tips")
    }

    print(f"Glossary entries: {total}")
    print(f"By module: {by_module}")
    print(f"By kind:   {by_kind}")

    if missing:
        print(f"FAIL: {len(missing)} keys are missing a description:")
        for key in missing[:20]:
            print(f"  - {key}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return 1

    if total == 0:
        print("FAIL: glossary is empty")
        return 1

    print("OK: every glossary key has a meta-context description")
    return 0


if __name__ == "__main__":
    sys.exit(main())
