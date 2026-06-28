"""Referral code system for the Avalone platform.

Repositories and services are reusable from the portal, Avalone Finance and Avalone Work.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from avalone_core.database import Repository, Service


class ReferralRepository(Repository):
    """SQL access for referral codes and referral relationships."""

    def get_user_id_by_code(self, code: str) -> int | None:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT id FROM users WHERE referral_code = ?", (code.upper(),)
            ).fetchone()
        return row["id"] if row else None

    def get_code_by_user(self, user_id: int) -> str | None:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT referral_code FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if not row or not row["referral_code"]:
            return None
        return row["referral_code"]

    def set_code(self, user_id: int, code: str) -> None:
        with self._db.connection() as con:
            con.execute(
                "UPDATE users SET referral_code = ? WHERE id = ?", (code.upper(), user_id)
            )

    def get_referrer_id(self, invitee_id: int) -> int | None:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT referred_by FROM users WHERE id = ?", (invitee_id,)
            ).fetchone()
        return row["referred_by"] if row and row["referred_by"] else None

    def set_referred_by(self, invitee_id: int, referrer_id: int) -> None:
        with self._db.connection() as con:
            con.execute(
                "UPDATE users SET referred_by = ? WHERE id = ?", (referrer_id, invitee_id)
            )

    def record_referral(
        self, referrer_id: int, invitee_id: int, code_used: str | None, fingerprint: str | None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._db.connection() as con:
            con.execute(
                """INSERT INTO avalone_referrals
                   (referrer_id, invitee_id, code_used, device_fingerprint, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (referrer_id, invitee_id, code_used or "", fingerprint or "", now),
            )

    def list_invitees(self, referrer_id: int) -> list[dict[str, Any]]:
        with self._db.connection() as con:
            rows = con.execute(
                """SELECT u.id, u.login, u.email, r.created_at
                   FROM avalone_referrals r
                   JOIN users u ON u.id = r.invitee_id
                   WHERE r.referrer_id = ?
                   ORDER BY r.created_at DESC""",
                (referrer_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "login": r["login"],
                "email": r["email"] or "",
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def count_invitees(self, referrer_id: int) -> int:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT COUNT(*) FROM avalone_referrals WHERE referrer_id = ?", (referrer_id,)
            ).fetchone()
        return row[0] if row else 0


class ReferralService(Service):
    """Business logic for referral codes."""

    _CODE_LENGTH = 8
    _BASE_URL = "https://avalone.online"

    def __init__(
        self, repo: ReferralRepository | None = None, user_repo: Any | None = None
    ) -> None:
        self._repo = repo or ReferralRepository()
        self._user_repo = user_repo

    def _generate_code(self) -> str:
        while True:
            code = secrets.token_urlsafe(6)[: self._CODE_LENGTH].upper()
            if len(code) == self._CODE_LENGTH and not self._repo.get_user_id_by_code(code):
                return code

    def get_or_create_code(self, user_id: int) -> str:
        code = self._repo.get_code_by_user(user_id)
        if code:
            return code
        code = self._generate_code()
        self._repo.set_code(user_id, code)
        return code

    def resolve_code(self, code: str | None) -> int | None:
        if not code:
            return None
        return self._repo.get_user_id_by_code(code.strip())

    def apply_referral(
        self, invitee_id: int, code: str | None, fingerprint: str | None
    ) -> bool:
        code = (code or "").strip().upper()
        if not code:
            return False
        referrer_id = self._repo.get_user_id_by_code(code)
        if not referrer_id:
            return False
        if referrer_id == invitee_id:
            return False
        if self._repo.get_referrer_id(invitee_id):
            return False
        self._repo.set_referred_by(invitee_id, referrer_id)
        self._repo.record_referral(referrer_id, invitee_id, code, fingerprint)
        return True

    def stats(self, user_id: int) -> dict[str, Any]:
        code = self.get_or_create_code(user_id)
        invitees = self._repo.list_invitees(user_id)
        return {
            "code": code,
            "url": f"{self._BASE_URL}?ref={code}",
            "invitees_count": len(invitees),
            "invitees": invitees,
        }
