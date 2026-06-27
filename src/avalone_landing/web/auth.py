"""Avalone identity routes: login/password auth and session API."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

from pathlib import Path

from avalone_core import glossary_db as glossary
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Shell, build_id as ui_build_id
import avalone_core.ui
from avalone_landing.config import settings
from avalone_landing.core import users

router = APIRouter()
BASE = Path(__file__).parent
_UI_DIR = Path(avalone_core.ui.__file__).parent
templates = Jinja2Templates(directory=[str(BASE / "templates"), str(_UI_DIR / "templates")])
templates.env.globals["t"] = glossary.t
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry

_signer = URLSafeSerializer(settings().fernet_key, salt="avalone-session")
SESSION_COOKIE = "avalone_session"
SESSION_MAX_AGE_DAYS = 90


def _user_id_of(request: Request) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return 0
    try:
        return int(_signer.loads(token))
    except Exception:
        return 0


def _cookie_domain(request: Request) -> str | None:
    host = request.url.hostname or ""
    if host in ("localhost", "127.0.0.1"):
        return None
    return ".avalone.online"


def _issue_session(request: Request, resp: Response, user_id: int) -> None:
    resp.set_cookie(
        SESSION_COOKIE,
        _signer.dumps(str(user_id)),
        httponly=True,
        secure=True,
        samesite="none",
        domain=_cookie_domain(request),
        max_age=60 * 60 * 24 * SESSION_MAX_AGE_DAYS,
    )


def _clear_session(request: Request, resp: Response) -> None:
    resp.delete_cookie(
        SESSION_COOKIE,
        domain=_cookie_domain(request),
        path="/",
        samesite="none",
        secure=True,
        httponly=True,
    )


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _user_id_of(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login(request: Request):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    user_id = users.authenticate(login_field, pw)
    if user_id:
        next_url = str(form.get("next", "")).strip()
        if not next_url or not next_url.startswith(("http://", "https://", "/")):
            next_url = "/"
        resp = RedirectResponse(next_url, status_code=303)
        _issue_session(request, resp, user_id)
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": t('auth_error_invalid_credentials')}, status_code=401
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if _user_id_of(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register")
async def register(request: Request):
    form = await request.form()
    login_field = str(form.get("login", "")).strip()
    pw = str(form.get("password", ""))
    pw2 = str(form.get("password2", ""))
    invite = str(form.get("invite", "")).strip()

    error = None
    if not login_field or not pw:
        error = t('auth_error_required')
    elif pw != pw2:
        error = t('auth_error_password_mismatch')
    elif len(pw) < 6:
        error = t('auth_error_password_too_short')
    elif users.login_taken(login_field):
        error = t('auth_error_login_taken')

    if error:
        return templates.TemplateResponse(
            request, "register.html", {"error": error}, status_code=400
        )

    try:
        user_id = users.create_user(login_field, pw)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "register.html", {"error": str(e)}, status_code=400
        )

    resp = RedirectResponse("/", status_code=303)
    _issue_session(request, resp, user_id)
    return resp


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse("/", status_code=303)
    _clear_session(request, resp)
    return resp


@router.get("/auth/me")
async def auth_me(request: Request):
    user_id = _user_id_of(request)
    if not user_id:
        return JSONResponse({"error": t('error_unauthorized')}, status_code=401)
    u = users.get_user(user_id)
    if not u:
        return JSONResponse({"error": t('error_user_not_found')}, status_code=401)
    return {
        "id": u["id"],
        "login": u["login"],
        "email": u["email"],
        "created_at": u["created_at"],
    }


@router.get("/auth/refresh")
async def auth_refresh(request: Request):
    """Prolong the session cookie."""
    user_id = _user_id_of(request)
    if not user_id:
        return JSONResponse({"error": t('error_unauthorized')}, status_code=401)
    u = users.get_user(user_id)
    if not u:
        return JSONResponse({"error": t('error_user_not_found')}, status_code=401)
    resp = JSONResponse({"ok": True, "user": {"id": u["id"], "login": u["login"]}})
    _issue_session(request, resp, user_id)
    return resp


def _shell_context_for(request: Request, user, current_app: str = "portal", app_nav=None):
    branches = AvaloneRegistry.for_shell("ru")
    shell = Shell(current_app=current_app, user=user, branches=branches, app_nav=app_nav or [])
    return {
        "build_id": ui_build_id(),
        "user": user,
        "shell_html": shell.render(templates.env, request),
    }


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user_id = _user_id_of(request)
    if not user_id:
        return RedirectResponse("/login?next=/profile", status_code=303)
    u = users.get_user(user_id)
    if not u:
        return RedirectResponse("/login", status_code=303)
    ctx = _shell_context_for(request, u, current_app="portal")
    return templates.TemplateResponse(request, "profile.html", ctx)


@router.post("/profile/password")
async def change_password(request: Request):
    user_id = _user_id_of(request)
    if not user_id:
        return JSONResponse({"error": t('error_unauthorized')}, status_code=401)
    form = await request.form()
    current = str(form.get("current_password", ""))
    new_pw = str(form.get("new_password", ""))
    new_pw2 = str(form.get("new_password2", ""))

    def _profile_ctx(**extra):
        ctx = _shell_context_for(request, users.get_user(user_id), current_app="portal")
        ctx.update(extra)
        return ctx

    if new_pw != new_pw2:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=t('profile_password_mismatch')), status_code=400
        )
    try:
        ok = users.change_password(user_id, current, new_pw)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=str(e)), status_code=400
        )
    if not ok:
        return templates.TemplateResponse(
            request, "profile.html", _profile_ctx(error=t('profile_current_password_wrong')), status_code=400
        )
    return templates.TemplateResponse(
        request, "profile.html", _profile_ctx(success=t('profile_password_changed'))
    )
