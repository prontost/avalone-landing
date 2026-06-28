"""Shared shell rendering helper for Avalone portal pages."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from avalone_core.language_service import LanguageService
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Shell
import avalone_core.ui
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.user_service import UserService
from avalone_landing.web.widgets import AuthModal

_UI_DIR = Path(avalone_core.ui.__file__).parent
_UI_TEMPLATES_DIR = _UI_DIR / "templates"


def _auth_modal_context(request: Request, templates: Jinja2Templates, user: dict | None) -> str:
    mode = request.query_params.get("mode") or "login"
    if mode not in ("login", "register", "forgot", "reset"):
        mode = "login"
    token = request.query_params.get("token", "") if mode == "reset" else ""
    modal = AuthModal(mode=mode, token=token, user=user)
    return modal.render(templates.env, request)


def _session_context(request: Request) -> list[dict]:
    auth = AuthService()
    uids = auth.session_uids(request)
    if not uids:
        return []
    active_uid = auth.active_user_id(request)
    us = UserService()
    sessions: list[dict] = []
    for uid in uids:
        u = us.get_user(uid)
        if not u:
            continue
        sessions.append(
            {
                "id": u.id,
                "login": u.login,
                "name": u.name,
                "email": u.email,
                "is_admin": u.is_admin,
                "active": u.id == active_uid,
            }
        )
    return sessions


def render_shell_context(
    templates: Jinja2Templates,
    request: Request,
    user: dict | None,
    current_app: str = "portal",
    app_nav: list[dict] | None = None,
    build_id: str = "",
    lang: str = "ru",
    **extra: object,
) -> dict:
    """Return the context dict used by shell-based templates."""
    branches = AvaloneRegistry.for_shell(lang)
    sessions = _session_context(request)
    auth_modal_html = _auth_modal_context(request, templates, user)
    shell = Shell(
        current_app=current_app,
        user=user,
        sessions=sessions,
        auth_modal_html=auth_modal_html,
        branches=branches,
        app_nav=app_nav or [],
        lang=lang,
        **extra,
    )
    return {
        "build_id": build_id,
        "user": user,
        "sessions": sessions,
        "auth_modal_html": auth_modal_html,
        "lang": lang,
        "shell_html": shell.render(templates.env, request),
    }
