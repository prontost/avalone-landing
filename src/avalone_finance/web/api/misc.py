"""Counta API domain router."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from avalone_core import glossary_db as glossary
from avalone_core.device_service import DeviceService
from avalone_core.language_service import LanguageService
from avalone_core.referral_service import ReferralService
from avalone_finance.core import notify, security, tenant

log = logging.getLogger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd
            else (request.client.host if request.client else "?"))


@router.get("/me")
async def me():
    """Current user profile (for the PWA banner)."""
    from avalone_finance.core import tenant
    tid = tenant.require_current()
    u = tenant.get_user(tid)
    if not u:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return {"login": u["login"], "email": u["email"],
            "email_verified": u["email_verified"], "is_admin": tenant.is_admin(tid)}

@router.post("/send-verify-code")
async def send_verify_code(request: Request):
    """Send (or resend) a 6-digit email verification code. Rate-limited."""
    from avalone_finance.core import tenant
    ip = _client_ip(request)
    if not security.allow_verify(ip):
        return JSONResponse({"error": "rate_limit"}, status_code=429)
    tid = tenant.require_current()
    u = tenant.get_user(tid)
    if not u or not u.get("email"):
        return JSONResponse({"error": "no_email"}, status_code=400)
    code = security.new_code()
    tenant.set_verify_code(tid, code)
    settings = notify.get_settings() or {}
    lang = settings.get("lang") or "ru"
    if lang == "auto":
        lang = "ru"
    body = glossary.t("email_verify_body", lang=lang).replace("{code}", code)
    subject = glossary.t("email_verify_subject", lang=lang)
    ok = notify._send_email(u["email"], subject, body)
    return {"sent": ok}

@router.post("/verify-email")
async def verify_email(request: Request, payload: dict):
    """Verify the 6-digit code sent by email."""
    from avalone_finance.core import tenant
    ip = _client_ip(request)
    if not security.allow_verify(ip):
        return JSONResponse({"error": "rate_limit"}, status_code=429)
    tid = tenant.require_current()
    code = str(payload.get("code", "")).strip()
    if tenant.check_verify_code(tid, code):
        return {"verified": True}
    return JSONResponse({"error": "invalid_code"}, status_code=400)


@router.post("/lang")
async def set_language(request: Request):
    """Persist language preference for the current user and cookie."""
    body = await request.json()
    service = LanguageService()
    resolved = service._normalize(str(body.get("lang", "auto")).strip().lower())
    tid = tenant.require_current()
    service.set_user_language(tid, resolved)
    response = JSONResponse({"ok": True, "lang": resolved})
    response.set_cookie(
        "avalone_lang",
        resolved,
        max_age=60 * 60 * 24 * 365,
        path="/",
        samesite="lax",
        secure=True,
    )
    return response


@router.get("/referral/code")
async def referral_code():
    tid = tenant.require_current()
    code = ReferralService().get_or_create_code(tid)
    return {"code": code, "url": f"https://avalone.online?ref={code}"}


@router.get("/referral/stats")
async def referral_stats():
    tid = tenant.require_current()
    return ReferralService().stats(tid)


@router.post("/heartbeat")
async def heartbeat(request: Request):
    tid = tenant.require_current()
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip() or None
    screen = str(body.get("screen", "")).strip()
    platform = str(body.get("platform", "")).strip()
    seconds = body.get("seconds", 5)
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = 5
    result = DeviceService().heartbeat(
        tid,
        device_id,
        request.headers.get("user-agent", ""),
        screen,
        platform,
        _client_ip(request),
        seconds,
    )
    return result
