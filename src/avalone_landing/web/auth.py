"""Avalone identity routes: login/password auth and session API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from avalone_core import glossary_db as glossary
from avalone_core.device_service import DeviceService
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import build_id as ui_build_id
import avalone_core.ui
from avalone_landing.config import settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_service import UserService
from avalone_landing.web.auth_controller import AuthController, AuthResult
from avalone_landing.web.dependencies import (
    current_user,
    get_auth_controller,
    get_auth_service,
    get_device_service,
    get_mail_service,
    get_shell_context,
    get_user_service,
)
from avalone_landing.web.shell_context import ShellContext

router = APIRouter()
BASE = Path(__file__).parent
_UI_DIR = Path(avalone_core.ui.__file__).parent
templates = Jinja2Templates(directory=[str(BASE / "templates"), str(_UI_DIR / "templates")])
templates.env.globals["t"] = glossary.t
t = glossary.t
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry


def _profile_context(
    request: Request,
    shell_context: ShellContext,
    user_service: UserService,
    device_service: DeviceService,
    user: User,
    **extra: object,
) -> dict:
    u = user_service.get_user(user.id)
    ctx = _shell_context(
        request,
        shell_context,
        {"id": u.id, "login": u.login, "name": u.name, "email": u.email, "created_at": u.created_at,
         "is_admin": u.is_admin, "email_verified": u.email_verified} if u else None,
    )
    ctx["screen_time"] = device_service.screen_time_summary(user.id)
    ctx.update(extra)
    return ctx


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def _user_shell_dict(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "login": user.login,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at,
        "is_admin": user.is_admin,
        "email_verified": user.email_verified,
    }


def _shell_context(
    request: Request,
    shell_context: ShellContext,
    user: dict | None,
    **extra: object,
) -> dict:
    ctx = shell_context.build(
        templates,
        request,
        user,
        current_app="portal",
        app_nav=[],
        build_id=ui_build_id(),
    )
    for key, value in extra.items():
        ctx.setdefault(key, value)
    return ctx


def _anon_shell_context(
    request: Request, shell_context: ShellContext, **extra: object
) -> dict:
    """Shell context for anonymous portal pages (login/register/reset)."""
    ctx = _shell_context(request, shell_context, None)
    ctx.update(extra)
    return ctx


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    ctx: dict = {}
    if user is not None:
        ctx["already_user"] = {"id": user.id, "login": user.login, "name": user.name, "email": user.email}
    if request.query_params.get("reset") == "ok":
        ctx["success"] = t("reset_password_success")
    return templates.TemplateResponse(request, "login.html", _shell_context(request, shell_context, _user_shell_dict(user), **ctx))


@router.post("/login")
async def login(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
    active_user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    result = auth_controller.login(
        login_field, pw, active_user.id if active_user else 0
    )
    base_ctx = {"already_user": {"id": active_user.id, "login": active_user.login, "name": active_user.name, "email": active_user.email}} if active_user else {}
    if result.success:
        next_url = str(form.get("next", "")).strip()
        if not next_url or not next_url.startswith(("http://", "https://", "/")):
            next_url = "/"
        resp = RedirectResponse(next_url, status_code=303)
        auth_controller.issue_session(request, resp, result.user_id)
        return resp
    if result.already_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            _shell_context(request, shell_context, _user_shell_dict(active_user), info=t("auth_already_active"), **base_ctx),
            status_code=200,
        )
    return templates.TemplateResponse(
        request,
        "login.html",
        _shell_context(request, shell_context, _user_shell_dict(active_user), error=t(result.error), **base_ctx),
        status_code=result.error_code,
    )


@router.post("/api/auth/login")
async def api_login(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
):
    body = await request.json()
    login_field = str(body.get("login", "")).strip()
    pw = str(body.get("password", ""))
    result = auth_controller.login(login_field, pw)
    if not result.success:
        return JSONResponse({"error": t(result.error)}, status_code=result.error_code)
    resp = JSONResponse({"ok": True, "next": "/"})
    auth_controller.issue_session(request, resp, result.user_id)
    return resp


@router.post("/api/auth/forgot-password")
async def api_forgot_password(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
):
    body = await request.json()
    login_or_email = str(body.get("login_or_email", "")).strip()
    result = auth_controller.request_password_reset(login_or_email)
    if not result.success:
        return JSONResponse({"error": t(result.error)}, status_code=result.error_code)
    return JSONResponse({"ok": True, "message": t("reset_email_sent_generic")})


@router.post("/api/auth/reset-password")
async def api_reset_password(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
):
    body = await request.json()
    token = str(body.get("token", ""))
    pw = str(body.get("password", ""))
    pw2 = str(body.get("password2", ""))

    result = auth_controller.reset_password(token, pw, pw2)
    if not result.success:
        return JSONResponse({"error": t(result.error)}, status_code=result.error_code)

    resp = JSONResponse({"ok": True, "next": "/"})
    auth_controller.issue_session(request, resp, result.user_id)
    return resp


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    return templates.TemplateResponse(request, "forgot_password.html", _shell_context(request, shell_context, _user_shell_dict(user)))


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
    active_user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    form = await request.form()
    login_or_email = str(form.get("login_or_email", "")).strip()
    ctx: dict = {}
    result = auth_controller.request_password_reset(login_or_email)
    if not result.success:
        ctx["error"] = t(result.error)
    elif result.reset_url:
        ctx["success"] = t("reset_email_sent")
        if not settings().smtp_host:
            ctx["reset_url"] = result.reset_url
    else:
        ctx["success"] = t("reset_email_sent_generic")
    return templates.TemplateResponse(request, "forgot_password.html", _shell_context(request, shell_context, _user_shell_dict(active_user), **ctx))


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
    active_user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    token = request.query_params.get("token", "")
    result = auth_controller.reset_password(token, "", "")
    if not result.success:
        return templates.TemplateResponse(
            request, "reset_password.html", _shell_context(request, shell_context, _user_shell_dict(active_user), error=t(result.error)), status_code=400
        )
    return templates.TemplateResponse(request, "reset_password.html", _shell_context(request, shell_context, _user_shell_dict(active_user), token=token))


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
    active_user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    form = await request.form()
    token = str(form.get("token", ""))
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))

    result = auth_controller.reset_password(token, pw, pw2)
    if not result.success:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            _shell_context(request, shell_context, _user_shell_dict(active_user), token=token, error=t(result.error)),
            status_code=result.error_code,
        )

    # Log the user in immediately so the SSO cookie is available for Avalone Finance/Avalone Work.
    resp = RedirectResponse("/", status_code=303)
    auth_controller.issue_session(request, resp, result.user_id)
    return resp


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    prefilled_ref = request.query_params.get("ref", "").strip()
    return templates.TemplateResponse(
        request, "register.html", _shell_context(request, shell_context, _user_shell_dict(user), prefilled_ref=prefilled_ref)
    )


@router.post("/register")
async def register(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
    active_user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))
    invite = str(form.get("invite", "")).strip()

    result = auth_controller.register(
        login_field, pw, pw2, invite, active_user.id if active_user else 0
    )
    if not result.success:
        return templates.TemplateResponse(
            request,
            "register.html",
            _shell_context(request, shell_context, _user_shell_dict(active_user), error=t(result.error)),
            status_code=result.error_code,
        )

    resp = RedirectResponse("/", status_code=303)
    auth_controller.issue_session(request, resp, result.user_id)
    return resp


@router.post("/api/auth/register")
async def api_register(
    request: Request,
    auth_controller: AuthController = Depends(get_auth_controller),
):
    body = await request.json()
    login_field = str(body.get("login", "")).strip()
    pw = str(body.get("password", ""))
    pw2 = str(body.get("password2", ""))
    invite = str(body.get("invite", "")).strip()

    result = auth_controller.register(login_field, pw, pw2, invite)
    if not result.success:
        return JSONResponse({"error": t(result.error)}, status_code=result.error_code)
    resp = JSONResponse({"ok": True, "next": "/"})
    auth_controller.issue_session(request, resp, result.user_id)
    return resp


@router.get("/logout")
async def logout(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    resp = RedirectResponse("/", status_code=303)
    auth_service.clear_active_session(request, resp)
    return resp


@router.post("/switch-user")
async def switch_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    form = await request.form()
    try:
        target_id = int(form.get("user_id", 0))
    except Exception:
        target_id = 0
    if not target_id:
        return RedirectResponse("/", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    auth_service.switch_active(request, resp, target_id)
    return resp


@router.get("/auth/me")
async def auth_me(
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_id = auth_service.active_user_id(request)
    if not user_id:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    user = user_service.get_user(user_id)
    if not user:
        return JSONResponse({"error": t("error_user_not_found")}, status_code=401)
    return {
        "id": user.id,
        "login": user.login,
        "name": user.name,
        "email": user.email,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
    }


@router.get("/auth/refresh")
async def auth_refresh(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
):
    """Prolong the session cookie."""
    user_id = auth_service.active_user_id(request)
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
    device_service: DeviceService = Depends(get_device_service),
    shell_context: ShellContext = Depends(get_shell_context),
):
    if user is None:
        return RedirectResponse("/login?next=/profile", status_code=303)
    u = user_service.get_user(user.id)
    if not u:
        return RedirectResponse("/login", status_code=303)
    ctx = _profile_context(request, shell_context, user_service, device_service, u)
    return templates.TemplateResponse(request, "profile.html", ctx)


@router.post("/profile/name")
async def update_profile_name(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
):
    if user is None:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    user_service.update_name(user.id, name)
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/email")
async def update_profile_email(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
    mail_service: MailService = Depends(get_mail_service),
    device_service: DeviceService = Depends(get_device_service),
    shell_context: ShellContext = Depends(get_shell_context),
):
    if user is None:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return templates.TemplateResponse(
            request, "profile.html",
            _profile_context(request, shell_context, user_service, device_service, user, error=t("profile_email_invalid")), status_code=400
        )
    user_service.update_email(user.id, email)
    code = user_service.generate_email_verification_code(user.id)
    subject = t("profile_verify_email_subject")
    body = t("profile_verify_email_body").format(code=code)
    try:
        mail_service.send_email(email, subject, body)
    except Exception as exc:
        return templates.TemplateResponse(
            request, "profile.html",
            _profile_context(request, shell_context, user_service, device_service, user, error=t("profile_verify_email_send_failed").format(error=str(exc))),
            status_code=500,
        )
    return templates.TemplateResponse(
        request, "profile.html",
        _profile_context(request, shell_context, user_service, device_service, user, success=t("profile_verify_email_sent"), pending_email_verification=True)
    )


@router.post("/profile/verify-email")
async def verify_profile_email(
    request: Request,
    user: User = Depends(current_user),
    user_service: UserService = Depends(get_user_service),
    device_service: DeviceService = Depends(get_device_service),
    shell_context: ShellContext = Depends(get_shell_context),
):
    if user is None:
        return JSONResponse({"error": t("error_unauthorized")}, status_code=401)
    form = await request.form()
    code = str(form.get("code", "")).strip()
    if user_service.verify_email_code(user.id, code):
        return templates.TemplateResponse(
            request, "profile.html", _profile_context(request, shell_context, user_service, device_service, user, success=t("profile_email_verified_success"))
        )
    return templates.TemplateResponse(
        request, "profile.html",
        _profile_context(request, shell_context, user_service, device_service, user, error=t("profile_verify_email_invalid")), status_code=400
    )
