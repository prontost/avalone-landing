"""Tests for user/job interactions (hide, like, bookmark)."""

from __future__ import annotations

from avalone_landing.core.jobs.interaction_repository import UserJobInteractionRepository
from avalone_landing.core.jobs.models import JobPost
from avalone_landing.core.jobs.repository import JobPostRepository
from avalone_landing.core.jobs.service import JobPostService


def _save_sample_post(external_guid: str) -> None:
    repo = JobPostRepository()
    repo.save(
        JobPost(
            external_guid=external_guid,
            source_site="koreabridge.net",
            source_url=f"https://example.com/{external_guid}",
            title=f"Job {external_guid}",
            description_html="",
            description_text="",
            content_hash=f"hash-{external_guid}",
            country="KR",
        )
    )


def test_upsert_like() -> None:
    repo = UserJobInteractionRepository()
    interaction = repo.upsert(user_id=1, external_guid="guid-1", liked=True)
    assert interaction.liked_at is not None
    assert interaction.hidden_at is None
    assert interaction.bookmarked_at is None

    cleared = repo.upsert(user_id=1, external_guid="guid-1", liked=False)
    assert cleared.liked_at is None


def test_upsert_preserves_other_flags() -> None:
    repo = UserJobInteractionRepository()
    repo.upsert(user_id=2, external_guid="guid-2", hidden=True)
    interaction = repo.upsert(user_id=2, external_guid="guid-2", bookmarked=True)
    assert interaction.hidden_at is not None
    assert interaction.bookmarked_at is not None


def test_get_for_user_returns_only_users_rows() -> None:
    repo = UserJobInteractionRepository()
    repo.upsert(user_id=3, external_guid="a", liked=True)
    repo.upsert(user_id=4, external_guid="b", liked=True)

    rows = repo.get_for_user(3, ["a", "b"])
    assert set(rows.keys()) == {"a"}


def test_list_hidden_and_bookmarked() -> None:
    repo = UserJobInteractionRepository()
    repo.upsert(user_id=5, external_guid="hidden-1", hidden=True)
    repo.upsert(user_id=5, external_guid="hidden-2", hidden=True)
    repo.upsert(user_id=5, external_guid="saved-1", bookmarked=True)

    hidden = repo.list_hidden(5)
    assert set(hidden) == {"hidden-1", "hidden-2"}

    bookmarked = repo.list_bookmarked(5)
    assert bookmarked == ["saved-1"]


def test_service_hidden_guids_filter_feed() -> None:
    _save_sample_post("visible-post")
    _save_sample_post("hidden-post")

    service = JobPostService()
    service.apply_interaction(user_id=10, external_guid="hidden-post", hidden=True)

    hidden_guids = service.hidden_guids(user_id=10)
    assert "hidden-post" in hidden_guids

    all_posts = service.list_recent(limit=100, exclude_guids=list(hidden_guids))
    guids = {p.external_guid for p in all_posts}
    assert "visible-post" in guids
    assert "hidden-post" not in guids


def test_service_bookmarked_only_feed() -> None:
    _save_sample_post("bookmarked-post")
    _save_sample_post("plain-post")

    service = JobPostService()
    service.apply_interaction(user_id=11, external_guid="bookmarked-post", bookmarked=True)

    bookmarked_guids = list(service.bookmarked_guids(user_id=11))
    posts = service.list_recent(limit=100, include_only_guids=bookmarked_guids)
    assert len(posts) == 1
    assert posts[0].external_guid == "bookmarked-post"


def test_bulk_interactions() -> None:
    _save_sample_post("bulk-a")
    _save_sample_post("bulk-b")
    _save_sample_post("bulk-c")

    service = JobPostService()
    count = service.apply_bulk_interactions(
        user_id=20,
        external_guids=["bulk-a", "bulk-b", "bulk-c"],
        hidden=True,
    )
    assert count == 3

    hidden = service.hidden_guids(user_id=20)
    assert hidden == {"bulk-a", "bulk-b", "bulk-c"}

    # Clear one flag via bulk and add another flag.
    service.apply_bulk_interactions(
        user_id=20,
        external_guids=["bulk-a", "bulk-b"],
        hidden=False,
        bookmarked=True,
    )
    hidden = service.hidden_guids(user_id=20)
    bookmarked = service.bookmarked_guids(user_id=20)
    assert hidden == {"bulk-c"}
    assert bookmarked == {"bulk-a", "bulk-b"}
