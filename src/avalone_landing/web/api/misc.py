"""Miscellaneous portal JSON API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from avalone_core import glossary_db as glossary
from avalone_core.device_service import DeviceService
from avalone_core.language_service import LanguageService
from avalone_core.referral_service import ReferralService
from avalone_landing.config import settings
from avalone_landing.core.feedback_service import FeedbackService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_service import UserService
from avalone_landing.web.dependencies import (
    current_user,
    get_device_service,
    get_feedback_service,
    get_language_service,
    get_mail_service,
    get_referral_service,
    get_user_service,
)

router = APIRouter()
t = glossary.t


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


@router.post("/api/lang")
async def set_language(
    request: Request,
    user: User | None = Depends(current_user),
    language_service: LanguageService = Depends(get_language_service),
):
    body = await request.json()
    lang = str(body.get("lang", "auto")).strip().lower()
    language_service.detect(request)  # warm resolution
    resolved = language_service._normalize(lang)

    if user is not None:
        language_service.set_user_language(user.id, resolved)

    response = JSONResponse({"ok": True, "lang": resolved})
    response.set_cookie(
        "avalone_lang",
        resolved,
        max_age=60 * 60 * 24 * 365,
        path="/",
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


@router.get("/api/referral/code")
async def referral_code(
    user: User | None = Depends(current_user),
    referral_service: ReferralService = Depends(get_referral_service),
):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    code = referral_service.get_or_create_code(user.id)
    return {"code": code, "url": f"{settings().web_base_url}?ref={code}"}


@router.get("/api/referral/stats")
async def referral_stats(
    user: User | None = Depends(current_user),
    referral_service: ReferralService = Depends(get_referral_service),
):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return referral_service.stats(user.id)


@router.post("/api/heartbeat")
async def heartbeat(
    request: Request,
    user: User | None = Depends(current_user),
    device_service: DeviceService = Depends(get_device_service),
):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip() or None
    screen = str(body.get("screen", "")).strip()
    platform = str(body.get("platform", "")).strip()
    seconds = body.get("seconds", 5)
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = 5
    user_agent = request.headers.get("user-agent", "")
    result = device_service.heartbeat(
        user.id,
        device_id,
        user_agent,
        screen,
        platform,
        _client_ip(request),
        seconds,
    )
    return result


@router.post("/api/feedback")
async def submit_feedback(
    request: Request,
    user: User | None = Depends(current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    body = await request.json()
    message = str(body.get("message", "")).strip()
    contact = str(body.get("contact", "")).strip()[:255]
    source_page = str(body.get("source_page", "")).strip()[:255] or request.headers.get("referer", "")
    if not message or len(message) < 2:
        return JSONResponse({"error": "message_too_short"}, status_code=400)
    if len(message) > 4000:
        return JSONResponse({"error": "message_too_long"}, status_code=400)

    feedback_service.submit(
        user.id if user else None,
        source_page,
        contact,
        message,
    )
    return {"ok": True}


@router.post("/api/request-password-reset")
async def request_password_reset_for_current_user(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
    mail_service: MailService = Depends(get_mail_service),
):
    if user is None:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    if not user.email or not user.email_verified:
        return JSONResponse({"error": t("profile_reset_email_required")}, status_code=400)
    result = user_service.request_password_reset(user.login)
    if not result:
        return JSONResponse({"error": t("error_user_not_found")}, status_code=404)
    reset_user, token = result
    reset_url = f"{settings().web_base_url}/reset-password?token={token}"
    subject = t("reset_email_subject")
    body = t("reset_email_body").format(login=reset_user.login, url=reset_url)
    try:
        mail_service.send_email(reset_user.email, subject, body)
    except Exception as exc:
        return JSONResponse(
            {"error": t("profile_reset_send_failed").format(error=str(exc))},
            status_code=500,
        )
    return {"ok": True}
