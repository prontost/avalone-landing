"""Persistence layer for aggregated job postings."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from avalone_core.db import connection

from .models import JobPost


class JobPostRepository:
    """Store and retrieve ``JobPost`` rows from the unified Avalone database."""

    def save(self, post: JobPost) -> int:
        """Insert a post or update it if the external GUID already exists."""
        row = self._post_to_row(post)
        columns = [
            "external_guid",
            "source_site",
            "source_url",
            "title",
            "title_translated",
            "description_html",
            "description_text",
            "description_translated",
            "employer",
            "contact_phone",
            "contact_email",
            "visa_type",
            "location",
            "job_type",
            "posted_at",
            "parsed_at",
            "raw_json",
        ]
        placeholders = ", ".join(["?"] * len(columns))
        updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c != "external_guid")
        sql = (
            f"INSERT INTO work_job_posts ({', '.join(columns)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(external_guid) DO UPDATE SET {updates}"
        )
        with connection() as con:
            cur = con.execute(sql, row)
            con.commit()
            return cur.lastrowid or 0

    def list_recent(self, limit: int = 100) -> list[JobPost]:
        """Return the most recent posts, newest first."""
        sql = (
            "SELECT * FROM work_job_posts "
            "ORDER BY COALESCE(posted_at, parsed_at) DESC "
            "LIMIT ?"
        )
        with connection() as con:
            rows = con.execute(sql, (limit,)).fetchall()
        return [self._row_to_post(r) for r in rows]

    def list_untranslated(self, limit: int = 100) -> list[JobPost]:
        """Return posts that have no translated title yet, oldest first."""
        sql = (
            "SELECT * FROM work_job_posts "
            "WHERE COALESCE(title_translated, '') = '' "
            "ORDER BY COALESCE(posted_at, parsed_at) ASC "
            "LIMIT ?"
        )
        with connection() as con:
            rows = con.execute(sql, (limit,)).fetchall()
        return [self._row_to_post(r) for r in rows]

    def update_translations(
        self,
        external_guid: str,
        title_translated: str,
        description_translated: str,
    ) -> None:
        with connection() as con:
            con.execute(
                "UPDATE work_job_posts SET title_translated = ?, description_translated = ? "
                "WHERE external_guid = ?",
                (title_translated, description_translated, external_guid),
            )
            con.commit()

    def count(self) -> int:
        with connection() as con:
            row = con.execute("SELECT COUNT(*) AS n FROM work_job_posts").fetchone()
        return row["n"] if row else 0

    def _post_to_row(self, post: JobPost) -> tuple[Any, ...]:
        return (
            post.external_guid,
            post.source_site,
            post.source_url,
            post.title,
            post.title_translated,
            post.description_html,
            post.description_text,
            post.description_translated,
            post.employer,
            post.contact_phone,
            post.contact_email,
            post.visa_type,
            post.location,
            post.job_type,
            post.posted_at.isoformat() if post.posted_at else None,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(post.raw, ensure_ascii=False) if post.raw else None,
        )

    def _row_to_post(self, row: sqlite3.Row) -> JobPost:
        posted_at = None
        if row["posted_at"]:
            try:
                posted_at = datetime.fromisoformat(row["posted_at"])
            except ValueError:
                posted_at = None
        raw = {}
        if row["raw_json"]:
            try:
                raw = json.loads(row["raw_json"])
            except json.JSONDecodeError:
                raw = {}
        return JobPost(
            external_guid=row["external_guid"],
            source_site=row["source_site"],
            source_url=row["source_url"],
            title=row["title"],
            description_html=row["description_html"] or "",
            description_text=row["description_text"] or "",
            posted_at=posted_at,
            author=raw.get("creator", ""),
            raw=raw,
            title_translated=row["title_translated"] or "",
            description_translated=row["description_translated"] or "",
            employer=row["employer"] or "",
            contact_phone=row["contact_phone"] or "",
            contact_email=row["contact_email"] or "",
            visa_type=row["visa_type"] or "",
            location=row["location"] or "",
            job_type=row["job_type"] or "",
        )
