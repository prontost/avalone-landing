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


def _apply_batch(
    service: JobPostService,
    batch: list[Any],
    mapping: dict[str, dict[str, str]],
) -> int:
    applied = 0
    for post in batch:
        item = mapping.get(post.external_guid)
        if not item:
            _log(f"No translation returned for {post.external_guid}")
            continue
        service.repository.update_translations(
            post.external_guid,
            item.get("title_translated", ""),
            item.get("description_translated", ""),
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
            applied = _apply_batch(service, untranslated, mapping)
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
    parser.add_argument("--lang", default="ru", choices=["ru", "en", "ko"], help="Target language")
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

    _log("Translation worker started.")
    stats = _translate_loop(service, args, deadline)
    _log(
        f"Done. {stats['translated']} postings translated "
        f"in {stats['batches']} batches ({stats['failures']} failures)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
