"""Parsers for external Korean job boards."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import JobPost

_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


class BaseJobParser(ABC):
    """Abstract base for a job-board parser."""

    @property
    @abstractmethod
    def source_site(self) -> str:
        """Human-readable source identifier (used for filtering)."""

    @abstractmethod
    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        """Download and parse recent job postings."""


class KoreabridgeRSSParser(BaseJobParser):
    """Fetch and parse https://koreabridge.net/jobs.xml."""

    URL = "https://koreabridge.net/jobs.xml"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "koreabridge.net"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text, max_age_days)

    def parse(self, xml_text: str, max_age_days: int = 14) -> list[JobPost]:
        root = ET.fromstring(xml_text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        posts: list[JobPost] = []
        for item in root.findall(".//item"):
            title = self._text(item, "title")
            link = self._text(item, "link")
            guid = self._text(item, "guid")
            description = html.unescape(self._text(item, "description"))
            posted_at = self._parse_pubdate(self._text(item, "pubDate"))

            if posted_at is not None and posted_at < cutoff:
                continue

            author = self._text(item, "dc:creator", ns=_NS)
            posts.append(
                JobPost(
                    external_guid=guid or link,
                    source_site=self.source_site,
                    source_url=link,
                    title=title,
                    description_html=description,
                    description_text=self._html_to_text(description),
                    posted_at=posted_at,
                    author=author,
                    raw={
                        "title": title,
                        "description": description,
                        "pubDate": self._text(item, "pubDate"),
                        "creator": author,
                    },
                )
            )
        return posts

    def _text(self, item: ET.Element, tag: str, ns: dict[str, str] | None = None) -> str:
        element = item.find(tag, ns) if ns else item.find(tag)
        return (element.text or "").strip() if element is not None else ""

    def _parse_pubdate(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc)
        except ValueError:
            return None

    def _html_to_text(self, html_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class AlbamonParser(BaseJobParser):
    """Fetch and parse the Albamon mobile homepage.

    Albamon is a major Korean part-time / arbeit job board. The mobile
    homepage embeds the job list inside ``window.__NEXT_DATA__``.
    """

    URL = "https://m.albamon.com/"
    USER_AGENT = (
        "Mozilla/5.0 (Linux; Android 10; SM-G973F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "albamon.com"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        # max_age_days is accepted for interface compatibility; Albamon
        # homepage always returns currently featured postings.
        del max_age_days
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text)

    def parse(self, html_text: str) -> list[JobPost]:
        data = self._extract_next_data(html_text)
        if not data:
            return []

        seen: set[int] = set()
        posts: list[JobPost] = []
        for item in self._walk_collections(data):
            recruit_no = item.get("recruitNo")
            if not recruit_no or recruit_no in seen:
                continue
            seen.add(recruit_no)

            title = (item.get("recruitTitle") or "").strip()
            area = (item.get("workplaceArea") or "").strip()
            company = (item.get("companyName") or "").strip()
            pay = (item.get("pay") or "").strip()
            pay_type = ""
            if isinstance(item.get("payType"), dict):
                pay_type = (item["payType"].get("description") or "").strip()

            posts.append(
                JobPost(
                    external_guid=f"albamon:{recruit_no}",
                    source_site=self.source_site,
                    source_url=f"https://m.albamon.com/jobs/detail/{recruit_no}",
                    title=title,
                    description_html="",
                    description_text=self._build_description(item),
                    author=company,
                    raw=item,
                    employer=company,
                    location=area,
                    salary=pay,
                    pay_type=pay_type,
                )
            )
        return posts

    def _extract_next_data(self, html_text: str) -> dict[str, Any] | None:
        match = re.search(
            r'id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html_text,
            re.DOTALL,
        )
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _walk_collections(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        queries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [])
        )
        for query in queries:
            state = query.get("state", {})
            payload = state.get("data", {})
            if isinstance(payload, dict) and isinstance(payload.get("collection"), list):
                items.extend(payload["collection"])
            elif isinstance(payload, list):
                items.extend(payload)
        return items

    def _build_description(self, item: dict[str, Any]) -> str:
        parts = [
            (item.get("payType") or {}).get("description", ""),
            item.get("pay", ""),
            item.get("workplaceArea", ""),
            item.get("companyName", ""),
        ]
        return "\n".join(p for p in parts if p).strip()


class MultiSourceParser(BaseJobParser):
    """Aggregate posts from all configured sources."""

    def __init__(self, parsers: list[BaseJobParser] | None = None) -> None:
        self.parsers = parsers or [KoreabridgeRSSParser(), AlbamonParser()]

    @property
    def source_site(self) -> str:
        return "multi"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        posts: list[JobPost] = []
        for parser in self.parsers:
            try:
                posts.extend(parser.fetch(max_age_days))
            except Exception:  # noqa: BLE001
                # One source failing should not block the others.
                continue
        return posts
