"""Signed session cookie handling for the Avalone portal."""

from __future__ import annotations

from fastapi import Request, Response
from itsdangerous import URLSafeSerializer

from avalone_core.database import Service

from avalone_landing.config import Settings, settings


class AuthService(Service):
    """Signs, verifies and clears the `avalone_session` cookie."""

    SESSION_COOKIE = "avalone_session"
    SESSION_MAX_AGE_DAYS = 90
    SALT = "avalone-session"

    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or settings()
        self._signer = URLSafeSerializer(self._cfg.fernet_key, salt=self.SALT)

    def user_id_of(self, request: Request) -> int:
        token = request.cookies.get(self.SESSION_COOKIE)
        if not token:
            return 0
        try:
            return int(self._signer.loads(token))
        except Exception:
            return 0

    def cookie_domain(self, request: Request) -> str | None:
        host = request.url.hostname or ""
        if host in ("localhost", "127.0.0.1"):
            return None
        return ".avalone.online"

    def issue_session(self, request: Request, response: Response, user_id: int) -> None:
        response.set_cookie(
            self.SESSION_COOKIE,
            self._signer.dumps(str(user_id)),
            httponly=True,
            secure=True,
            samesite="none",
            domain=self.cookie_domain(request),
            max_age=60 * 60 * 24 * self.SESSION_MAX_AGE_DAYS,
        )

    def clear_session(self, request: Request, response: Response) -> None:
        response.delete_cookie(
            self.SESSION_COOKIE,
            domain=self.cookie_domain(request),
            path="/",
            samesite="none",
            secure=True,
            httponly=True,
        )
