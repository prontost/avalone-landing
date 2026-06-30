"""Orchestration: fetch, extract, translate, and store job postings."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .models import JobPost
from .parser import AlbamonParser, BaseJobParser, KoreabridgeRSSParser, MultiSourceParser
from .repository import JobPostRepository


class JobPostService:
    """High-level service for the Work module's job aggregation."""

    def __init__(
        self,
        parser: BaseJobParser | None = None,
        repository: JobPostRepository | None = None,
    ) -> None:
        self.parser = parser or MultiSourceParser()
        self.repository = repository or JobPostRepository()

    def fetch_and_store(self, max_age_days: int = 14) -> dict[str, int]:
        """Fetch recent posts from all sources, extract fields, and persist them."""
        now = datetime.now(timezone.utc)
        posts = self.parser.fetch(max_age_days=max_age_days)
        for post in posts:
            self._extract_fields(post)
            # Albamon does not expose posting dates; freeze the first time we see it.
            if post.posted_at is None and isinstance(self.parser, AlbamonParser):
                post.posted_at = now
            self.repository.save(post)
        return {"fetched": len(posts), "stored": len(posts)}

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
        return self.repository.list_recent(
            limit=limit,
            offset=offset,
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
        )

    def count_recent(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
    ) -> int:
        return self.repository.count_recent(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
        )

    def list_untranslated(self, limit: int = 100) -> list[JobPost]:
        return self.repository.list_untranslated(limit)

    def _extract_fields(self, post: JobPost) -> None:
        """Pull employer, phone, email, visa, location, and job type from the text."""
        text = post.description_text

        # Employer: prefer already-set employer, then RSS author.
        post.employer = post.employer or post.author or ""

        # Phone numbers (Korean mobile / landline patterns).
        phones = re.findall(
            r"\b0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}\b",
            text,
        )
        post.contact_phone = phones[0] if phones else ""

        # Emails.
        emails = re.findall(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            text,
        )
        post.contact_email = emails[0] if emails else ""

        # Visa types commonly mentioned in Korea job ads.
        visa_pattern = re.compile(
            r"\b(E-?[2-7]|F-?[2-6]|F-?5|H-?1|D-?[2-4]|D-?10)\b",
            re.IGNORECASE,
        )
        visas = sorted({v.upper() for v in visa_pattern.findall(text)})
        visas = [self._normalize_visa(v) for v in visas]
        post.visa_type = ", ".join(visas) if visas else ""

        # Location: simple keyword extraction if not already set.
        if not post.location:
            post.location = self._extract_location(text + " " + post.title)

    @staticmethod
    def _normalize_visa(value: str) -> str:
        value = value.upper()
        if "-" not in value and len(value) >= 2:
            value = value[0] + "-" + value[1:]
        return value

    @staticmethod
    def _extract_location(text: str) -> str:
        known = [
            "Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju",
            "Ulsan", "Suwon", "Goyang", "Yongin", "Bucheon", "Ansan",
            "Anyang", "Seongnam", "Gimhae", "Changwon", "Jeonju", "Cheongju",
            "Pohang", "Gyeongju", "Jeju", "Gangnam", "Hongdae", "Itaewon",
            "Bundang", "Haeundae", "Dongrae", "Dongnae", "PNU", "SNU",
            "Gimpo", "Pyeongtaek", "Nationwide", "Gyeonggi-do", "Gyeonggi",
        ]
        found = []
        lower = text.lower()
        for city in known:
            if city.lower() in lower:
                found.append(city)
        return ", ".join(found) if found else ""
