"""Avalone SSO integration: shared signed cookie across avalone.online domain.

The landing app issues ``avalone_session`` cookie. The finance module reads it,
verifies the signature with the shared key, and returns the Avalone user_id. The
user_id IS the finance ``tenant_id``; no local mapping table is needed.
"""

from fastapi import Request
from itsdangerous import URLSafeSerializer

from avalone_finance.core.config import settings

_signer = URLSafeSerializer(
    settings().avalone_fernet_key or settings().fernet_key,
    salt="avalone-session",
)


def user_id_of(request: Request) -> int:
    """Return Avalone user_id from cookie, or 0 if missing/invalid."""
    token = request.cookies.get(settings().avalone_cookie_name)
    if not token:
        return 0
    try:
        return int(_signer.loads(token))
    except Exception:
        return 0
