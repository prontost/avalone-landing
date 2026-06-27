"""Avalone identity routes: login/password auth and session API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from avalone_core import glossary_db as glossary
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import build_id as ui_build_id
import avalone_core.ui
from avalone_landing.config import settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_service import UserService
from avalone_landing.web.dependencies import (
    current_user,
    get_auth_service,
    get_mail_service,
    get_user_service,
)
from avalone_landing.web.shell_context import render_shell_context

router = APIRouter()
BASE = Path(__file__).parent
_UI_DIR = Path(avalone_core.ui.__file__).parent
templates = Jinja2Templates(directory=[str(BASE / "templates"), str(_UI_DIR / "templates")])
templates.env.globals["t"] = glossary.t
t = glossary.t
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def _shell_context(request: Request, user: dict | None) -> dict:
    return render_shell_context(
        templates,
        request,
        user,
        current_app="portal",
        app_nav=[],
        build_id=ui_build_id(),
    )


def _anon_shell_context(request: Request, **extra: object) -> dict:
    """Shell context for anonymous portal pages (login/register/reset)."""
    ctx = _shell_context(request, None)
    ctx.update(extra)
    return ctx


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user: User | None = Depends(current_user),
):
    if user is not None or auth_service.user_id_of(request):
        return RedirectResponse("/", status_code=303)
    ctx: dict = {}
    if request.query_params.get("reset") == "ok":
        ctx["success"] = t("reset_password_success")
    return templates.TemplateResponse(request, "login.html", _anon_shell_context(request, **ctx))


@router.post("/login")
async def login(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    user = user_service.authenticate(login_field, pw)
    if user:
        next_url = str(form.get("next", "")).strip()
        if not next_url or not next_url.startswith(("http://", "https://", "/")):
            next_url = "/"
        resp = RedirectResponse(next_url, status_code=303)
        auth_service.issue_session(request, resp, user.id)
        return resp
    return templates.TemplateResponse(
        request, "login.html", _anon_shell_context(request, error=t("auth_error_invalid_credentials")), status_code=401
    )


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user: User | None = Depends(current_user),
):
    if user is not None or auth_service.user_id_of(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "forgot_password.html", _anon_shell_context(request))


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    user_service: UserService = Depends(get_user_service),
    mail_service: MailService = Depends(get_mail_service),
):
    form = await request.form()
    login_or_email = str(form.get("login_or_email", "")).strip()
    ctx: dict = {}
    if login_or_email:
        result = user_service.request_password_reset(login_or_email)
        if result:
            user, token = result
            if user.email:
                reset_url = f"{settings().web_base_url}/reset-password?token={token}"
                subject = t("reset_email_subject")
                body = t("reset_email_body").format(login=user.login, url=reset_url)
                cfg = settings()
                if cfg.smtp_host:
                    # Production: send via configured SMTP relay.
                    try:
                        mail_service.send_email(user.email, subject, body)
                        ctx["success"] = t("reset_email_sent")
                    except Exception as exc:
                        ctx["error"] = t("reset_email_failed").format(error=str(exc))
                        ctx["reset_url"] = reset_url
                else:
                    # Dev/local fallback: attempt local sendmail, but always expose
                    # the link because delivery is unreliable without a real relay.
                    try:
                        mail_service.send_email(user.email, subject, body)
                    except Exception:
                        pass
                    ctx["success"] = t("reset_email_sent")
                    ctx["reset_url"] = reset_url
            else:
                # User exists but has no email on file.
                ctx["success"] = t("reset_email_sent_no_email")
        else:
            # Do not reveal that the user does not exist.
            ctx["success"] = t("reset_email_sent_generic")
    else:
        ctx["error"] = t("reset_error_required")
    return templates.TemplateResponse(request, "forgot_password.html", _anon_shell_context(request, **ctx))


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    user_service: UserService = Depends(get_user_service),
):
    token = request.query_params.get("token", "")
    user = user_service.get_user_by_reset_token(token) if token else None
    if not user:
        return templates.TemplateResponse(
            request, "reset_password.html", _anon_shell_context(request, error=t("reset_token_invalid")), status_code=400
        )
    return templates.TemplateResponse(request, "reset_password.html", _anon_shell_context(request, token=token))


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
):
    form = await request.form()
    token = str(form.get("token", ""))
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))

    user = user_service.get_user_by_reset_token(token) if token else None
    if not user:
        return templates.TemplateResponse(
            request, "reset_password.html", _anon_shell_context(request, error=t("reset_token_invalid")), status_code=400
        )

    error = None
    if not pw:
        error = t("auth_error_required")
    elif pw != pw2:
        error = t("auth_error_password_mismatch")
    elif len(pw) < 6:
        error = t("auth_error_password_too_short")

    if error:
        return templates.TemplateResponse(
            request, "reset_password.html", _anon_shell_context(request, token=token, error=error), status_code=400
        )

    try:
        user = user_service.reset_password(token, pw)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "reset_password.html", _anon_shell_context(request, token=token, error=str(e)), status_code=400
        )

    if user is None:
        return templates.TemplateResponse(
            request, "reset_password.html", _anon_shell_context(request, token=token, error=t("reset_token_invalid")), status_code=400
        )

    # Log the user in immediately so the SSO cookie is available for Counta/Routa.
    resp = RedirectResponse("/", status_code=303)
    auth_service.issue_session(request, resp, user.id)
    return resp


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user: User | None = Depends(current_user),
):
    if user is not None or auth_service.user_id_of(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "register.html", _anon_shell_context(request))


@router.post("/register")
async def register(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))
    invite = str(form.get("invite", "")).strip()

    error = None
    if not login_field or not pw:
        error = t("auth_error_required")
    elif pw != pw2:
        error = t("auth_error_password_mismatch")
    elif len(pw) < 6:
        error = t("auth_error_password_too_short")
    elif user_service.login_taken(login_field):
        error = t("auth_error_login_taken")

    if error:
        return templates.TemplateResponse(
            request, "register.html", _anon_shell_context(request, error=error), status_code=400
        )

    try:
        user_id = user_service.create_user(login_field, pw)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "register.html", _anon_shell_context(request, error=str(e)), status_code=400
        )

    resp = RedirectResponse("/", status_code=303)
    auth_service.issue_session(request, resp, user_id)
    return resp


@router.get("/logout")
async def logout(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    resp = RedirectResponse("/", status_code=303)
    auth_service.clear_session(request, resp)
    return resp


@router.get("/auth/me")
async def auth_me(
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_id = auth_service.user_id_of(request)
    if not user_id:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    user = user_service.get_user(user_id)
    if not user:
        return JSONResponse({"error": t("error_user_not_found")}, status_code=401)
    return {
        "id": user.id,
        "login": user.login,
        "email": user.email,
        "created_at": user.created_at,
    }


@router.get("/auth/refresh")
async def auth_refresh(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
):
    """Prolong the session cookie."""
    user_id = auth_service.user_id_of(request)
    if not user_id:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    user = user_service.get_user(user_id)
    if not user:
        return JSONResponse({"error": t("error_user_not_found")}, status_code=401)
    resp = JSONResponse({"ok": True, "user": {"id": user.id, "login": user.login}})
    auth_service.issue_session(request, resp, user.id)
    return resp


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
):
    if user is None:
        return RedirectResponse("/login?next=/profile", status_code=303)
    u = user_service.get_user(user.id)
    if not u:
        return RedirectResponse("/login", status_code=303)
    ctx = _shell_context(request, {"id": u.id, "login": u.login, "email": u.email, "created_at": u.created_at})
    return templates.TemplateResponse(request, "profile.html", ctx)


@router.post("/profile/password")
async def change_password(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
):
    if user is None:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    form = await request.form()
    current = str(form.get("current_password", ""))
    new_pw = str(form.get("new_password", ""))
    new_pw2 = str(form.get("new_password2", ""))

    def _profile_ctx(**extra):
        u = user_service.get_user(user.id)
        ctx = _shell_context(
            request,
            {"id": u.id, "login": u.login, "email": u.email, "created_at": u.created_at} if u else None,
        )
        ctx.update(extra)
        return ctx

    if new_pw != new_pw2:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=t("profile_password_mismatch")), status_code=400
        )
    try:
        ok = user_service.change_password(user.id, current, new_pw)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=str(e)), status_code=400
        )
    if not ok:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=t("profile_current_password_wrong")), status_code=400
        )
    return templates.TemplateResponse(
        request, "profile.html", _profile_ctx(success=t("profile_password_changed"))
    )
