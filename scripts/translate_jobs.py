#!/usr/bin/env python3
"""Translate job postings in the Avalone DB using the local Kimi CLI.

Usage:
    uv run python scripts/translate_jobs.py [--lang ru] [--batch 5]

The script fetches untranslated posts from work_job_posts, sends them in
batches to `kimi -p`, parses the returned JSON, and writes the translations
back to the database.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from avalone_core.db import migrate
from avalone_landing.core.jobs.service import JobPostService


KIMI_CLI = shutil.which("kimi") or str(Path.home() / ".kimi-code" / "bin" / "kimi")


def _build_prompt(posts: list[Any], target_lang: str, source_lang: str) -> str:
    lang_names = {"ru": "Russian", "en": "English", "ko": "Korean"}
    target_name = lang_names.get(target_lang, target_lang)
    source_name = lang_names.get(source_lang, source_lang)
    payload = [
        {
            "external_guid": p.external_guid,
            "title": p.title,
            "description": p.description_text,
        }
        for p in posts
    ]
    return (
        f"You are a professional translator. Translate the following job postings "
        f"from {source_name} to {target_name}. "
        "Return ONLY a valid JSON array. Each object must contain exactly the keys "
        "external_guid, title_translated, description_translated. "
        "Preserve the structure and line breaks of the description. "
        "Do not include explanations, markdown formatting, or any text outside the JSON array.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _extract_json(text: str) -> list[dict[str, str]] | None:
    """Find the first JSON array in ``text`` and parse it."""
    start = text.find("[")
    if start == -1:
        return None
    end = text.rfind("]")
    if end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _call_kimi(prompt: str) -> str:
    cmd = [
        KIMI_CLI,
        "-p",
        prompt,
        "--output-format",
        "text",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kimi CLI failed: {result.stderr or result.stdout}")
    return result.stdout


def _translate_batch(posts: list[Any], target_lang: str, source_lang: str) -> dict[str, dict[str, str]]:
    prompt = _build_prompt(posts, target_lang, source_lang)
    output = _call_kimi(prompt)
    data = _extract_json(output)
    if data is None:
        raise RuntimeError("Could not extract JSON array from kimi output")
    return {item["external_guid"]: item for item in data}


def main() -> int:
    parser = ArgumentParser(description="Translate job postings via Kimi CLI")
    parser.add_argument("--lang", default="ru", choices=["ru", "en", "ko"], help="Target language")
    parser.add_argument("--source", default="en", choices=["ru", "en", "ko"], help="Source language")
    parser.add_argument("--batch", type=int, default=5, help="Posts per kimi prompt")
    parser.add_argument("--limit", type=int, default=0, help="Translate at most N posts (0 = all)")
    args = parser.parse_args()

    migrate()
    service = JobPostService()
    untranslated = service.list_untranslated(limit=args.limit if args.limit > 0 else 10000)
    if not untranslated:
        print("No untranslated postings found.")
        return 0

    total = len(untranslated)
    translated = 0
    for i in range(0, total, args.batch):
        batch = untranslated[i : i + args.batch]
        print(f"Translating batch {i // args.batch + 1}/{(total - 1) // args.batch + 1} ({len(batch)} posts)...")
        try:
            mapping = _translate_batch(batch, args.lang, args.source)
        except Exception as exc:
            print(f"Batch failed: {exc}", file=sys.stderr)
            continue
        for post in batch:
            item = mapping.get(post.external_guid)
            if not item:
                print(f"  No translation returned for {post.external_guid}", file=sys.stderr)
                continue
            service.repository.update_translations(
                post.external_guid,
                item.get("title_translated", ""),
                item.get("description_translated", ""),
            )
            translated += 1

    print(f"Translated {translated}/{total} postings to {args.lang}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
