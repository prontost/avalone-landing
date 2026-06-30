"""Tests for the Avalone Work job-aggregation module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from avalone_landing.core.jobs.models import JobPost
from avalone_landing.core.jobs.parser import AlbamonParser, KoreabridgeRSSParser
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
    parser = KoreabridgeRSSParser()
    posts = parser.parse(_sample_xml([old, recent]), max_age_days=14)

    assert len(posts) == 1
    assert posts[0].external_guid == "job-1"
    assert "010-1234-5678" in posts[0].description_text


def test_albamon_parser_extracts_jobs() -> None:
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"dehydratedState":{"queries":[{"state":{"data":{"collection":[
        {"recruitNo": 12345, "recruitTitle": "카페 알바", "workplaceArea": "강남구", "companyName": "ABC카페", "pay": "12,000원", "payType": {"description": "시급"}}
    ]}}}]}}}}
    </script>
    </body></html>
    """
    parser = AlbamonParser()
    posts = parser.parse(html)

    assert len(posts) == 1
    assert posts[0].title == "카페 알바"
    assert posts[0].source_site == "albamon.com"
    assert posts[0].salary == "12,000원"
    assert posts[0].pay_type == "시급"
    assert "albamon.com/jobs/detail/12345" in posts[0].source_url


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
        salary="3.0M",
        pay_type="월급",
    )
    repo.save(post)
    rows = repo.list_recent(limit=10)
    guids = {r.external_guid for r in rows}
    assert "repo-test" in guids


def test_repository_filters_by_source_and_query() -> None:
    repo = JobPostRepository()
    repo.save(
        JobPost(
            external_guid="filter-seoul",
            source_site="albamon.com",
            source_url="https://example.com/seoul",
            title="Seoul cafe job",
            description_html="",
            description_text="",
            location="Seoul",
            salary="12,000원",
        )
    )
    repo.save(
        JobPost(
            external_guid="filter-busan",
            source_site="koreabridge.net",
            source_url="https://example.com/busan",
            title="Busan teacher job",
            description_html="",
            description_text="",
            location="Busan",
        )
    )
    seoul_jobs = repo.list_recent(source_site="albamon.com", query="cafe")
    assert len(seoul_jobs) == 1
    assert seoul_jobs[0].external_guid == "filter-seoul"


def test_fetch_preserves_existing_translation_and_posted_at() -> None:
    repo = JobPostRepository()
    posted = datetime(2026, 6, 1, tzinfo=timezone.utc)
    repo.save(
        JobPost(
            external_guid="preserve-test",
            source_site="koreabridge.net",
            source_url="https://example.com/preserve",
            title="Original",
            description_html="<p>Original body</p>",
            description_text="Original body",
            title_translated="Перевод",
            description_translated="Переведённый текст",
            posted_at=posted,
        )
    )
    # Re-save with empty translations and a different date — upsert must keep the existing ones.
    repo.save(
        JobPost(
            external_guid="preserve-test",
            source_site="koreabridge.net",
            source_url="https://example.com/preserve",
            title="Original",
            description_html="<p>Original body</p>",
            description_text="Original body",
            title_translated="",
            description_translated="",
            posted_at=datetime.now(timezone.utc),
        )
    )
    posts = [p for p in repo.list_recent(limit=100) if p.external_guid == "preserve-test"]
    assert len(posts) == 1
    post = posts[0]
    assert post.title_translated == "Перевод"
    assert post.description_translated == "Переведённый текст"
    assert post.posted_at == posted


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
