"""Tests for the Avalone Work job-aggregation module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from avalone_landing.core.jobs.models import JobPost
from avalone_landing.core.jobs.parser import AlbamonParser, JobKoreaParser, KoreabridgeRSSParser, SaraminParser
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
    assert posts[0].country == "KR"


def test_albamon_parser_extracts_jobs() -> None:
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"dehydratedState":{"queries":[{"state":{"data":{"collection":[
        {"recruitNo": 12345, "recruitTitle": "카페 알바", "workplaceArea": "강남구", "companyName": "ABC카페", "pay": "12,000원", "payType": {"description": "시급", "key": "HOURLY_WAGE"}}
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
    assert posts[0].job_type == "Part-time / hourly"
    assert posts[0].country == "KR"
    assert "albamon.com/jobs/detail/12345" in posts[0].source_url


def test_saramin_parser_extracts_jobs() -> None:
    html = """
    <div class="item_recruit">
      <div class="job_tit"><a href="/zf_user/jobs/relay/view?rec_idx=12345">Software Engineer</a></div>
      <div class="corp_name"><a>ACME Corp</a></div>
      <div class="job_condition">서울 강남구 경력무관 학력무관 정규직</div>
      <div class="job_date"><span class="date">~ 08/11(화)</span></div>
    </div>
    """
    parser = SaraminParser()
    posts = parser.parse(html)

    assert len(posts) == 1
    assert posts[0].external_guid == "saramin:12345"
    assert posts[0].title == "Software Engineer"
    assert posts[0].employer == "ACME Corp"
    assert posts[0].job_type == "Full-time"
    assert posts[0].location == "서울 강남구"
    assert posts[0].country == "KR"
    assert posts[0].posted_at is None  # Saramin dates are deadlines, not posting dates
    assert "saramin.co.kr" in posts[0].source_url


def test_jobkorea_parser_extracts_jobs() -> None:
    html = r'''
    <script>self.__next_f.push([1, "1:\"$Sreact.fragment\"\n7:I[...]\n0:{\"company\":{\"companyName\":\"ExampleCorp\"},\"job\":{\"jobId\":\"99999\",\"title\":\"Backend Engineer\",\"jobUrl\":\"/Recruit/GI_Read/99999\",\"firstPostedAt\":\"2026-06-15T10:00:00+09:00\",\"workplaceLocation\":\"서울 강남구\",\"payType\":\"ANNUALLY_SALARY\",\"payRangeStart\":\"5000\",\"payRangeEnd\":\"7000\",\"employmentType\":\"PERMANENT\"}}"]);
    </script>
    '''
    parser = JobKoreaParser()
    posts = parser.parse(html)

    assert len(posts) == 1
    assert posts[0].external_guid == "jobkorea:99999"
    assert posts[0].title == "Backend Engineer"
    assert posts[0].employer == "ExampleCorp"
    assert posts[0].job_type == "Full-time"
    assert "5000 ~ 7000 만원" in posts[0].salary
    assert "jobkorea.co.kr" in posts[0].source_url
    assert posts[0].country == "KR"


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
    service._compute_content_hash(post)

    assert post.contact_phone == "010-9876-5432"
    assert post.contact_email == "hr@school.kr"
    assert "E-2" in post.visa_type
    assert post.employer == "School HR"
    assert len(post.content_hash) == 64


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
        content_hash="abc123",
        country="KR",
    )
    row_id, status = repo.save(post)
    assert status == "inserted"
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
            content_hash="hash1",
            country="KR",
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
            content_hash="hash2",
            country="KR",
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
            content_hash="hash-preserve",
            country="KR",
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
            content_hash="hash-preserve",
            country="KR",
        )
    )
    posts = [p for p in repo.list_recent(limit=100) if p.external_guid == "preserve-test"]
    assert len(posts) == 1
    post = posts[0]
    assert post.title_translated == "Перевод"
    assert post.description_translated == "Переведённый текст"
    assert post.posted_at == posted


def test_repository_list_untranslated_respects_max_age() -> None:
    repo = JobPostRepository()
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=30)
    recent = now - timedelta(days=2)
    repo.save(
        JobPost(
            external_guid="untranslated-old",
            source_site="koreabridge.net",
            source_url="https://example.com/old",
            title="Old untranslated",
            description_html="",
            description_text="",
            posted_at=old,
            content_hash="hash-old",
            country="KR",
        )
    )
    repo.save(
        JobPost(
            external_guid="untranslated-recent",
            source_site="koreabridge.net",
            source_url="https://example.com/recent",
            title="Recent untranslated",
            description_html="",
            description_text="",
            posted_at=recent,
            content_hash="hash-recent",
            country="KR",
        )
    )
    all_untranslated = repo.list_untranslated(limit=100)
    guids = {p.external_guid for p in all_untranslated}
    assert {"untranslated-old", "untranslated-recent"}.issubset(guids)

    fresh_untranslated = repo.list_untranslated(limit=100, max_age_days=14)
    fresh_guids = {p.external_guid for p in fresh_untranslated}
    assert "untranslated-recent" in fresh_guids
    assert "untranslated-old" not in fresh_guids


def test_content_hash_avoids_unnecessary_update() -> None:
    repo = JobPostRepository()
    post = JobPost(
        external_guid="dedup-test",
        source_site="albamon.com",
        source_url="https://example.com/dedup",
        title="Same",
        description_html="",
        description_text="Same body",
        content_hash="dedup-hash",
        country="KR",
    )
    _, status1 = repo.save(post)
    assert status1 == "inserted"
    _, status2 = repo.save(post)
    assert status2 == "unchanged"


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
            content_hash="render-hash",
            country="KR",
        )
    )
    client = TestClient(app)
    response = client.get("/work")
    assert response.status_code == 200
    assert "Тест отображения" in response.text
