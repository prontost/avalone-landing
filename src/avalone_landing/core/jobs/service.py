"""Orchestration: fetch, extract, translate, and store job postings."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from .interaction_repository import UserJobInteractionRepository
from .models import JobPost
from .parser import AlbamonParser, BaseJobParser, KoreabridgeRSSParser, MultiSourceParser
from .repository import JobPostRepository


class JobPostService:
    """High-level service for the Work module's job aggregation."""

    def __init__(
        self,
        parser: BaseJobParser | None = None,
        repository: JobPostRepository | None = None,
        interaction_repository: UserJobInteractionRepository | None = None,
    ) -> None:
        self.parser = parser or MultiSourceParser()
        self.repository = repository or JobPostRepository()
        self.interactions = interaction_repository or UserJobInteractionRepository()

    def fetch_and_store(self, max_age_days: int = 14) -> dict[str, int]:
        """Fetch recent posts from all sources, extract fields, and persist them.

        Uses content hashing to avoid rewriting identical postings every run.
        """
        now = datetime.now(timezone.utc)
        posts = self.parser.fetch(max_age_days=max_age_days)
        stats = {"fetched": len(posts), "inserted": 0, "updated": 0, "unchanged": 0}
        for post in posts:
            self._extract_fields(post)
            # Albamon does not expose posting dates; freeze the first time we see it.
            if post.posted_at is None and isinstance(self.parser, AlbamonParser):
                post.posted_at = now
            self._compute_content_hash(post)
            _, status = self.repository.save(post)
            stats[status] += 1
        return stats

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
        country: str | None = None,
        query_lang: str = "ru",
        exclude_guids: list[str] | None = None,
        include_only_guids: list[str] | None = None,
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
            country=country,
            query_lang=query_lang,
            exclude_guids=exclude_guids,
            include_only_guids=include_only_guids,
        )

    def count_recent(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
        country: str | None = None,
        query_lang: str = "ru",
        exclude_guids: list[str] | None = None,
        include_only_guids: list[str] | None = None,
    ) -> int:
        return self.repository.count_recent(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
            country=country,
            query_lang=query_lang,
            exclude_guids=exclude_guids,
            include_only_guids=include_only_guids,
        )

    def list_untranslated(
        self,
        limit: int = 100,
        max_age_days: int | None = None,
        lang: str = "ru",
    ) -> list[JobPost]:
        return self.repository.list_untranslated(limit, max_age_days, lang=lang)

    def attach_translations(
        self, posts: list[JobPost], lang: str
    ) -> dict[str, dict[str, str]]:
        """Return a mapping external_guid -> {title, description} for ``lang``."""
        guids = [p.external_guid for p in posts]
        return self.repository.get_translations(guids, lang)

    def attach_interactions(
        self, user_id: int | None, posts: list[JobPost]
    ) -> dict[str, object]:
        """Return a mapping external_guid -> UserJobInteraction for ``user_id``."""
        if user_id is None or not posts:
            return {}
        guids = [p.external_guid for p in posts]
        return self.interactions.get_for_user(user_id, guids)

    def apply_interaction(
        self,
        user_id: int,
        external_guid: str,
        *,
        liked: bool | None = None,
        hidden: bool | None = None,
        bookmarked: bool | None = None,
    ) -> object:
        """Set or clear a single interaction flag for a user and post."""
        return self.interactions.upsert(
            user_id, external_guid, liked=liked, hidden=hidden, bookmarked=bookmarked
        )

    def apply_bulk_interactions(
        self,
        user_id: int,
        external_guids: list[str],
        *,
        liked: bool | None = None,
        hidden: bool | None = None,
        bookmarked: bool | None = None,
    ) -> int:
        """Apply the same interaction flag to many posts."""
        return self.interactions.upsert_many(
            user_id, external_guids, liked=liked, hidden=hidden, bookmarked=bookmarked
        )

    def hidden_guids(self, user_id: int) -> set[str]:
        """Return the set of post GUIDs hidden by the user."""
        return set(self.interactions.list_hidden(user_id, limit=-1))

    def bookmarked_guids(self, user_id: int) -> set[str]:
        """Return the set of post GUIDs bookmarked by the user."""
        return set(self.interactions.list_bookmarked(user_id, limit=-1))

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
    def _compute_content_hash(post: JobPost) -> None:
        payload = {
            "title": post.title,
            "description_text": post.description_text,
            "employer": post.employer,
            "location": post.location,
            "job_type": post.job_type,
            "salary": post.salary,
            "pay_type": post.pay_type,
            "visa_type": post.visa_type,
            "source_url": post.source_url,
        }
        post.content_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

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
