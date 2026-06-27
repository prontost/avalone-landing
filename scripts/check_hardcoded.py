"""Detect hardcoded user-facing Cyrillic strings in source files.

Scans Python and HTML/Jinja templates for Cyrillic text that is not inside a
comment or an allowed glossary seed file. Fails with a list of offending lines.

Run from repo root:
    python3 scripts/check_hardcoded.py [path...]

Default paths cover the Avalone portal + shared core.
"""

from __future__ import annotations

import re
import sys
import tokenize
from pathlib import Path

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
# HTML/Jinja/CSS block comments and JS line comments (//... but not URLs like http://).
HTML_COMMENT_RE = re.compile(r"<!--.*?-->|\{#.*?#\}|/\*.*?\*/|(?<![:/])//.*$", re.DOTALL | re.MULTILINE)
DATA_I_ATTR_RE = re.compile(r"\sdata-i(?:-[a-z]+)?=\s*['\"]")

# Files that intentionally contain translated glossary content.
ALLOWLIST_FILES = {
    "glossary_db.py",
    "ui_glossary.py",
    "glossary_seed.py",
}

# Maintenance scripts / local tooling — not shipped user-facing UI.
ALLOWLIST_PATH_SUFFIXES = {
    "scripts/build_glossary_seed.py",
    "scripts/check_i18n.py",
    "scripts/merge_owner_categories.py",
    "scripts/migrate_legacy_categories.py",
    "scripts/cleanup_owner_categories.py",
    "scripts/migrate_tenant_pk.py",
    "scripts/seed_all_catalogs.py",
    "src/counta/core/lexicon.py",
    "src/routa/core/lexicon.py",
}

# Specific internal identifiers / test markers that are not user-facing UI.
ALLOWLIST_PYTHON_STRINGS = {
    "налич", "касса", "банк", "кредит", "зарплат", "подработ", "проч",
    "other", "misc", "기타", "salary", "side", "part", "cash", "credit",
    "[A-ZА-Я]", "[a-zа-я]",
    "contract-test", "pwa e2e", "кпз e2e", "пробная",
    "прочее", "разобрать",
}

SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".ruff_cache", "migrations"}


def _is_allowed(path: Path) -> bool:
    if path.name in ALLOWLIST_FILES:
        return True
    for suffix in ALLOWLIST_PATH_SUFFIXES:
        if str(path).endswith(suffix):
            return True
    return False


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
        if part == "tests":
            return True
    return False


def _is_allowed_py_string(tok_str: str) -> bool:
    s = tok_str.strip("'\"")
    for fragment in ALLOWLIST_PYTHON_STRINGS:
        if fragment in s:
            return True
    return False


def _cyrillic_in_python_strings(path: Path) -> list[tuple[int, str]]:
    """Use tokenize to find Cyrillic inside non-docstring string literals."""
    offenses: list[tuple[int, str]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for tok_type, tok_str, (line, _), _, line_text in tokenize.generate_tokens(f.readline):
                if tok_type != tokenize.STRING:
                    continue
                # Skip module/class/function docstrings (triple-quoted).
                if tok_str.startswith(('"""', "'''")):
                    continue
                if CYRILLIC_RE.search(tok_str) and not _is_allowed_py_string(tok_str):
                    offenses.append((line, line_text.rstrip("\n")))
    except (SyntaxError, tokenize.TokenError) as e:
        print(f"WARN: could not tokenize {path}: {e}")
    return offenses


def _cyrillic_in_html(path: Path) -> list[tuple[int, str]]:
    """Find Cyrillic outside HTML/Jinja/CSS comments and data-i fallbacks."""
    offenses: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return offenses
    # Strip comments before scanning so translators' notes don't count.
    text_without_comments = HTML_COMMENT_RE.sub("", text)
    for lineno, raw_line in enumerate(text_without_comments.splitlines(), start=1):
        if not CYRILLIC_RE.search(raw_line):
            continue
        # Lines that contain data-i* attributes are allowed to have fallback
        # text; the real translation is applied client-side from I18N.
        if DATA_I_ATTR_RE.search(raw_line):
            continue
        offenses.append((lineno, raw_line.rstrip("\n")))
    return offenses


def scan(paths: list[Path]) -> dict[Path, list[tuple[int, str]]]:
    results: dict[Path, list[tuple[int, str]]] = {}
    for root in paths:
        for path in root.rglob("*"):
            if not path.is_file() or _is_allowed(path) or _should_skip(path):
                continue
            if path.suffix == ".py":
                offenses = _cyrillic_in_python_strings(path)
            elif path.suffix in {".html", ".jinja", ".jinja2"}:
                offenses = _cyrillic_in_html(path)
            else:
                continue
            if offenses:
                results[path] = offenses
    return results


def main() -> int:
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        root = Path(__file__).parent.parent
        paths = [
            root / "src" / "avalone_core",
            root / "src" / "avalone_landing",
        ]

    results = scan(paths)
    if not results:
        print("OK: no hardcoded Cyrillic strings found in scanned files")
        return 0

    total = sum(len(v) for v in results.values())
    print(f"FAIL: {total} hardcoded Cyrillic string(s) found")
    for path, offenses in sorted(results.items()):
        print(f"\n{path}")
        for lineno, line in offenses:
            print(f"  {lineno}: {line.strip()}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
