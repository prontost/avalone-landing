#!/usr/bin/env python3
"""Translate job postings in the Avalone DB using the local Kimi CLI.

Usage:
    uv run python scripts/translate_jobs.py [--lang ru] [--batch 5]

The script fetches untranslated posts from work_job_posts, sends them in
batches to `kimi -p`, parses the returned JSON, and writes the translations
back to the database.

Unlike a cron job, this is a single foreground worker: it translates one
batch, immediately picks the next batch, and continues until there are no
untranslated posts left, a limit is reached, or a timeout expires.  This keeps
translation quality high (one capable model) while still making steady
progress.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from avalone_core.db import migrate
from avalone_landing.core.jobs.service import JobPostService


KIMI_CLI = shutil.which("kimi") or str(Path.home() / ".kimi-code" / "bin" / "kimi")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _log(message: str) -> None:
    print(f"[{_now()}] {message}", flush=True)


def _build_prompt(posts: list[Any], target_lang: str, source_lang: str) -> str:
    lang_names = {"ru": "Russian", "en": "English", "ko": "Korean"}
    target_name = lang_names.get(target_lang, target_lang)
    payload = [
        {
            "external_guid": p.external_guid,
            "title": p.title,
            "description": p.description_text,
        }
        for p in posts
    ]
    return (
        f"You are a professional translator. Detect the source language of each job posting "
        f"(it is usually Korean or English) and translate it to {target_name}. "
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


def _is_already_target_language(text: str, target_lang: str) -> bool:
    """Return True if ``text`` already appears to be in the target language."""
    if not text:
        return False
    if target_lang == "ko":
        return bool(re.search(r"[\uac00-\ud7af]", text))
    if target_lang == "ru":
        return bool(re.search(r"[\u0400-\u04ff]", text))
    if target_lang == "en":
        # Consider English if it has Latin letters and no Hangul/Cyrillic.
        has_latin = bool(re.search(r"[a-zA-Z]", text))
        has_non_latin_script = bool(re.search(r"[\uac00-\ud7af\u0400-\u04ff]", text))
        return has_latin and not has_non_latin_script
    return False


def _apply_batch(
    service: JobPostService,
    batch: list[Any],
    mapping: dict[str, dict[str, str]],
    target_lang: str,
) -> int:
    applied = 0
    for post in batch:
        item = mapping.get(post.external_guid)
        title = (item.get("title_translated") or "").strip()
        description = (item.get("description_translated") or "").strip()

        # If the source is already in the target language, preserve the
        # original text instead of re-translating it.
        if _is_already_target_language(post.title, target_lang):
            title = post.title
        if _is_already_target_language(post.description_text, target_lang):
            description = post.description_text

        if not title or not description:
            if not item:
                _log(f"No translation returned for {post.external_guid}")
            else:
                _log(
                    f"Empty translation returned for {post.external_guid} "
                    f"(title={bool(title)}, desc={bool(description)})"
                )
            continue
        service.repository.update_translations(
            post.external_guid,
            title,
            description,
            lang=target_lang,
        )
        applied += 1
    return applied


def _translate_loop(
    service: JobPostService,
    args: Any,
    deadline: float | None,
) -> dict[str, int]:
    """Translate batches back-to-back until work runs out or a limit is hit."""
    stats = {"total_seen": 0, "translated": 0, "batches": 0, "failures": 0}

    while True:
        remaining_limit = None
        if args.limit > 0:
            remaining_limit = args.limit - stats["translated"]
            if remaining_limit <= 0:
                _log(f"Reached --limit {args.limit}; stopping.")
                break

        batch_limit = args.batch
        if remaining_limit is not None:
            batch_limit = min(batch_limit, remaining_limit)

        untranslated = service.list_untranslated(
            limit=batch_limit,
            max_age_days=args.max_age_days,
            lang=args.lang,
        )
        if not untranslated:
            _log("No untranslated postings left. Worker finished.")
            break

        if deadline is not None and time.time() >= deadline:
            _log("Translation timeout reached; stopping.")
            break

        stats["total_seen"] += len(untranslated)
        stats["batches"] += 1
        _log(
            f"Batch {stats['batches']}: translating {len(untranslated)} posts "
            f"({args.source} -> {args.lang})..."
        )

        try:
            mapping = _translate_batch(untranslated, args.lang, args.source)
            applied = _apply_batch(service, untranslated, mapping, args.lang)
        except Exception as exc:
            stats["failures"] += 1
            _log(f"Batch failed: {exc}")
            if stats["failures"] >= args.max_failures:
                _log(f"Reached {args.max_failures} consecutive failures; stopping.")
                break
            time.sleep(args.retry_delay)
            continue

        stats["failures"] = 0
        stats["translated"] += applied
        _log(f"Batch done: {applied}/{len(untranslated)} applied (total {stats['translated']}).")

        if args.loop:
            time.sleep(args.interval)
        else:
            # Without --loop, pause briefly between batches to avoid hammering the CLI.
            time.sleep(args.retry_delay)

    return stats


def main() -> int:
    parser = ArgumentParser(description="Translate job postings via Kimi CLI")
    parser.add_argument("--lang", default="ru", choices=["ru", "en", "ko", "all"], help="Target language ('all' rotates through ru, en, ko)")
    parser.add_argument("--source", default="en", choices=["ru", "en", "ko"], help="Source language")
    parser.add_argument("--batch", type=int, default=5, help="Posts per kimi prompt")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Translate at most N posts in this run (0 = no limit)",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Only translate posts newer than N days (limits spend on stale listings)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="Stop after N seconds regardless of remaining work (0 = no timeout)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep running: after draining the queue, sleep and wait for new posts",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds to sleep between checks in --loop mode",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=10,
        help="Seconds to wait after a failed batch before retrying",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=3,
        help="Stop after N consecutive batch failures",
    )
    args = parser.parse_args()

    migrate()
    service = JobPostService()

    deadline = None
    if args.timeout_seconds > 0:
        deadline = time.time() + args.timeout_seconds

    target_langs = ["ru", "en", "ko"] if args.lang == "all" else [args.lang]
    total_stats = {"total_seen": 0, "translated": 0, "batches": 0, "failures": 0}

    for target_lang in target_langs:
        args.lang = target_lang
        _log(f"Translation worker started for {target_lang}.")
        stats = _translate_loop(service, args, deadline)
        total_stats["total_seen"] += stats["total_seen"]
        total_stats["translated"] += stats["translated"]
        total_stats["batches"] += stats["batches"]
        total_stats["failures"] += stats["failures"]
        _log(
            f"Done for {target_lang}. {stats['translated']} postings translated "
            f"in {stats['batches']} batches ({stats['failures']} failures)."
        )

    _log(
        f"All done. {total_stats['translated']} postings translated "
        f"in {total_stats['batches']} batches ({total_stats['failures']} failures)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
