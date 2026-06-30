"""Persistence layer for aggregated job postings."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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
            "salary",
            "pay_type",
            "posted_at",
            "parsed_at",
            "raw_json",
        ]
        placeholders = ", ".join(["?"] * len(columns))
        # Preserve existing translations and first-seen posted date on re-fetch.
        preserve = {"title_translated", "description_translated", "posted_at"}
        updates = ", ".join(
            f"{c}=excluded.{c}" for c in columns if c != "external_guid" and c not in preserve
        )
        sql = (
            f"INSERT INTO work_job_posts ({', '.join(columns)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(external_guid) DO UPDATE SET {updates}"
        )
        with connection() as con:
            cur = con.execute(sql, row)
            con.commit()
            return cur.lastrowid or 0

    def list_recent(
        self,
        limit: int = 100,
        offset: int = 0,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
    ) -> list[JobPost]:
        """Return recent posts with optional filters."""
        where, params = self._build_where(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
        )

        sql = (
            "SELECT * FROM work_job_posts "
            + ("WHERE " + " AND ".join(where) if where else "")
            + " ORDER BY COALESCE(posted_at, parsed_at) DESC "
            + "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        with connection() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._row_to_post(r) for r in rows]

    def count_recent(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
    ) -> int:
        where, params = self._build_where(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
        )
        sql = (
            "SELECT COUNT(*) AS n FROM work_job_posts "
            + ("WHERE " + " AND ".join(where) if where else "")
        )
        with connection() as con:
            row = con.execute(sql, params).fetchone()
        return row["n"] if row else 0

    def _build_where(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
    ) -> tuple[list[str], list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        if source_site:
            where.append("source_site = ?")
            params.append(source_site)
        if location:
            where.append("(location LIKE ? OR title LIKE ? OR description_text LIKE ?)")
            like = f"%{location}%"
            params.extend([like, like, like])
        if max_age_days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
            where.append("COALESCE(posted_at, parsed_at) >= ?")
            params.append(cutoff)
        if query:
            q = f"%{query}%"
            where.append(
                "(title LIKE ? OR title_translated LIKE ? OR description_text LIKE ? "
                "OR description_translated LIKE ? OR employer LIKE ? OR location LIKE ?)"
            )
            params.extend([q, q, q, q, q, q])
        if visa_type:
            where.append("visa_type LIKE ?")
            params.append(f"%{visa_type}%")
        if job_type:
            where.append("(job_type LIKE ? OR title LIKE ? OR description_text LIKE ?)")
            j = f"%{job_type}%"
            params.extend([j, j, j])
        return where, params

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

    def list_sources(self) -> list[str]:
        """Return all distinct source_site values currently in the DB."""
        sql = "SELECT DISTINCT source_site FROM work_job_posts ORDER BY source_site"
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["source_site"] for r in rows if r["source_site"]]

    def list_locations(self) -> list[str]:
        """Return distinct non-empty location values."""
        sql = (
            "SELECT DISTINCT location FROM work_job_posts "
            "WHERE location IS NOT NULL AND location != '' ORDER BY location"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["location"] for r in rows]

    def list_pay_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT pay_type FROM work_job_posts "
            "WHERE pay_type IS NOT NULL AND pay_type != '' ORDER BY pay_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["pay_type"] for r in rows]

    def list_visa_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT visa_type FROM work_job_posts "
            "WHERE visa_type IS NOT NULL AND visa_type != '' ORDER BY visa_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return sorted({v.strip() for row in rows for v in row["visa_type"].split(",") if v.strip()})

    def list_job_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT job_type FROM work_job_posts "
            "WHERE job_type IS NOT NULL AND job_type != '' ORDER BY job_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["job_type"] for r in rows]

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
            post.salary,
            post.pay_type,
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
            salary=row["salary"] or "",
            pay_type=row["pay_type"] or "",
        )
