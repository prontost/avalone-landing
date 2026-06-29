"""Orchestration: fetch, extract, translate, and store job postings."""

from __future__ import annotations

import re

from .models import JobPost
from .parser import KoreabridgeRSSParser
from .repository import JobPostRepository


class JobPostService:
    """High-level service for the Work module's job aggregation."""

    def __init__(
        self,
        parser: KoreabridgeRSSParser | None = None,
        repository: JobPostRepository | None = None,
    ) -> None:
        self.parser = parser or KoreabridgeRSSParser()
        self.repository = repository or JobPostRepository()

    def fetch_and_store(self) -> dict[str, int]:
        """Fetch recent posts, extract fields, and persist them (no translation)."""
        posts = self.parser.fetch()
        for post in posts:
            self._extract_fields(post)
            self.repository.save(post)
        return {"fetched": len(posts), "stored": len(posts)}

    def list_recent(self, limit: int = 100) -> list[JobPost]:
        return self.repository.list_recent(limit)

    def list_untranslated(self, limit: int = 100) -> list[JobPost]:
        return self.repository.list_untranslated(limit)

    def _extract_fields(self, post: JobPost) -> None:
        """Pull employer, phone, email, visa, location, and job type from the text."""
        text = post.description_text

        # Employer: prefer the RSS author.
        post.employer = post.author or ""

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
            r"\b(E-?[2-7]|F-?[2-6]|F-?5|H-?1|D-?2|D-?4|D-?10)\b",
            re.IGNORECASE,
        )
        visas = sorted({v.upper().replace("-", "-") for v in visa_pattern.findall(text)})
        # Normalize e.g. "E2" -> "E-2".
        visas = [self._normalize_visa(v) for v in visas]
        post.visa_type = ", ".join(visas) if visas else ""

        # Location: simple keyword extraction.
        post.location = self._extract_location(text + " " + post.title)

        # Job type from categories is not available in the RSS teaser.
        post.job_type = ""

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
