"""Persistence layer for user/job interactions (hide, like, bookmark)."""

from __future__ import annotations

from datetime import datetime, timezone

from avalone_core.db import connection
from avalone_landing.core.jobs.models import UserJobInteraction


class UserJobInteractionRepository:
    """Store per-user hide/like/bookmark state for job postings."""

    def upsert(
        self,
        user_id: int,
        external_guid: str,
        liked: bool | None = None,
        hidden: bool | None = None,
        bookmarked: bool | None = None,
    ) -> UserJobInteraction:
        """Update interaction flags for a user and post.

        ``True`` sets the timestamp, ``False`` clears it, ``None`` leaves it
        unchanged.
        """
        now = datetime.now(timezone.utc).isoformat()
        with connection() as con:
            existing = con.execute(
                "SELECT liked_at, hidden_at, bookmarked_at FROM work_user_interactions "
                "WHERE user_id = ? AND external_guid = ?",
                (user_id, external_guid),
            ).fetchone()

            if existing:
                liked_at = _update_flag(existing["liked_at"], liked, now)
                hidden_at = _update_flag(existing["hidden_at"], hidden, now)
                bookmarked_at = _update_flag(existing["bookmarked_at"], bookmarked, now)
                con.execute(
                    """
                    UPDATE work_user_interactions
                    SET liked_at = ?, hidden_at = ?, bookmarked_at = ?, updated_at = ?
                    WHERE user_id = ? AND external_guid = ?
                    """,
                    (liked_at, hidden_at, bookmarked_at, now, user_id, external_guid),
                )
            else:
                liked_at = now if liked else None
                hidden_at = now if hidden else None
                bookmarked_at = now if bookmarked else None
                con.execute(
                    """
                    INSERT INTO work_user_interactions
                        (user_id, external_guid, liked_at, hidden_at, bookmarked_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, external_guid, liked_at, hidden_at, bookmarked_at, now),
                )
            con.commit()

        return self.get(user_id, external_guid)

    def upsert_many(
        self,
        user_id: int,
        external_guids: list[str],
        *,
        liked: bool | None = None,
        hidden: bool | None = None,
        bookmarked: bool | None = None,
    ) -> int:
        """Bulk update interaction flags for many posts at once.

        ``True`` sets the timestamp, ``False`` clears it, ``None`` leaves it
        unchanged. All rows share the same flag transition.
        """
        if not external_guids:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        liked_at = now if liked else None
        hidden_at = now if hidden else None
        bookmarked_at = now if bookmarked else None
        liked_flag = 1 if liked is True else (0 if liked is False else -1)
        hidden_flag = 1 if hidden is True else (0 if hidden is False else -1)
        bookmarked_flag = 1 if bookmarked is True else (0 if bookmarked is False else -1)
        rows = [
            (
                user_id,
                guid,
                liked_at,
                hidden_at,
                bookmarked_at,
                now,
                liked_flag,
                liked_flag,
                hidden_flag,
                hidden_flag,
                bookmarked_flag,
                bookmarked_flag,
            )
            for guid in external_guids
        ]
        with connection() as con:
            con.executemany(
                """
                INSERT INTO work_user_interactions
                    (user_id, external_guid, liked_at, hidden_at, bookmarked_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, external_guid) DO UPDATE SET
                    liked_at = CASE WHEN ? = 1 THEN EXCLUDED.liked_at
                                    WHEN ? = 0 THEN NULL
                                    ELSE liked_at END,
                    hidden_at = CASE WHEN ? = 1 THEN EXCLUDED.hidden_at
                                     WHEN ? = 0 THEN NULL
                                     ELSE hidden_at END,
                    bookmarked_at = CASE WHEN ? = 1 THEN EXCLUDED.bookmarked_at
                                         WHEN ? = 0 THEN NULL
                                         ELSE bookmarked_at END,
                    updated_at = EXCLUDED.updated_at
                """,
                rows,
            )
            con.commit()
        return len(external_guids)

    def get(self, user_id: int, external_guid: str) -> UserJobInteraction:
        with connection() as con:
            row = con.execute(
                "SELECT * FROM work_user_interactions WHERE user_id = ? AND external_guid = ?",
                (user_id, external_guid),
            ).fetchone()
        if not row:
            return UserJobInteraction(user_id=user_id, external_guid=external_guid)
        return self._row_to_interaction(row)

    def get_for_user(
        self, user_id: int, external_guids: list[str]
    ) -> dict[str, UserJobInteraction]:
        if not external_guids:
            return {}
        placeholders = ",".join("?" * len(external_guids))
        with connection() as con:
            rows = con.execute(
                f"SELECT * FROM work_user_interactions "
                f"WHERE user_id = ? AND external_guid IN ({placeholders})",
                (user_id, *external_guids),
            ).fetchall()
        return {row["external_guid"]: self._row_to_interaction(row) for row in rows}

    def list_hidden(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[str]:
        with connection() as con:
            rows = con.execute(
                "SELECT external_guid FROM work_user_interactions "
                "WHERE user_id = ? AND hidden_at IS NOT NULL "
                "ORDER BY hidden_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [row["external_guid"] for row in rows]

    def list_bookmarked(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[str]:
        with connection() as con:
            rows = con.execute(
                "SELECT external_guid FROM work_user_interactions "
                "WHERE user_id = ? AND bookmarked_at IS NOT NULL "
                "ORDER BY bookmarked_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [row["external_guid"] for row in rows]

    def _row_to_interaction(self, row) -> UserJobInteraction:
        return UserJobInteraction(
            user_id=row["user_id"],
            external_guid=row["external_guid"],
            liked_at=row["liked_at"],
            hidden_at=row["hidden_at"],
            bookmarked_at=row["bookmarked_at"],
            updated_at=row["updated_at"],
        )


def _update_flag(
    current: str | None, value: bool | None, now: str
) -> str | None:
    if value is True:
        return now
    if value is False:
        return None
    return current
