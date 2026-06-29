"""Tests for the Avalone Work job-aggregation module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from avalone_landing.core.jobs.models import JobPost
from avalone_landing.core.jobs.parser import KoreabridgeRSSParser
from avalone_landing.core.jobs.repository import JobPostRepository
from avalone_landing.core.jobs.service import JobPostService
from avalone_landing.web.app import app


def _sample_xml(pub_dates: list[datetime]) -> str:
    items = ""
    for i, dt in enumerate(pub_dates):
        items += f"""
    <item>
      <title>Job {i}</title>
      <link>https://koreabridge.net/jobs/job-{i}</link>
      <guid>job-{i}</guid>
      <description>&lt;p&gt;Description {i}. Contact: 010-1234-5678.&lt;/p&gt;</description>
      <pubDate>{dt.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>
      <dc:creator>author-{i}</dc:creator>
    </item>
"""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Jobs</title>
    {items}
  </channel>
</rss>
"""


def test_parser_filters_old_posts() -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    recent = now - timedelta(days=1)
    parser = KoreabridgeRSSParser(max_age_days=14)
    posts = parser.parse(_sample_xml([old, recent]))

    assert len(posts) == 1
    assert posts[0].external_guid == "job-1"
    assert "010-1234-5678" in posts[0].description_text


def test_service_extracts_contacts_and_visa() -> None:
    post = JobPost(
        external_guid="test-1",
        source_site="koreabridge.net",
        source_url="https://example.com/1",
        title="Teacher wanted",
        description_html="<p>Need E2 visa. Call 010-9876-5432 or email hr@school.kr</p>",
        description_text="Need E2 visa. Call 010-9876-5432 or email hr@school.kr",
        author="School HR",
    )
    service = JobPostService(parser=KoreabridgeRSSParser(), repository=JobPostRepository())
    service._extract_fields(post)

    assert post.contact_phone == "010-9876-5432"
    assert post.contact_email == "hr@school.kr"
    assert "E-2" in post.visa_type
    assert post.employer == "School HR"


def test_repository_saves_and_lists() -> None:
    repo = JobPostRepository()
    post = JobPost(
        external_guid="repo-test",
        source_site="koreabridge.net",
        source_url="https://example.com/repo",
        title="Title",
        description_html="<p>Body</p>",
        description_text="Body",
        title_translated="Заголовок",
        description_translated="Текст",
        contact_phone="010-1111-2222",
    )
    repo.save(post)
    rows = repo.list_recent(limit=10)
    guids = {r.external_guid for r in rows}
    assert "repo-test" in guids


def test_work_index_renders_feed() -> None:
    repo = JobPostRepository()
    repo.save(
        JobPost(
            external_guid="render-test",
            source_site="koreabridge.net",
            source_url="https://example.com/render",
            title="Render Test",
            description_html="<p>HTML</p>",
            description_text="Text",
            title_translated="Тест отображения",
            description_translated="Текст объявления",
        )
    )
    client = TestClient(app)
    response = client.get("/work")
    assert response.status_code == 200
    assert "Тест отображения" in response.text
