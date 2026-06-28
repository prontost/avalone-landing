"""Shared shell rendering helper for Avalone portal pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from avalone_core.language_service import LanguageService
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Shell
import avalone_core.ui
from avalone_landing.config import Settings, settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.user_service import UserService
from avalone_landing.web.widgets import AuthModal

_UI_DIR = Path(avalone_core.ui.__file__).parent
_UI_TEMPLATES_DIR = _UI_DIR / "templates"


@dataclass
class ShellContext:
    """Builds the context dict used by every shell-based portal page.

    Dependencies are injected via the constructor so routes receive a ready
    instance through FastAPI ``Depends``.
    """

    auth_service: AuthService
    user_service: UserService
    language_service: LanguageService
    cfg: Settings

    def build(
        self,
        templates: Jinja2Templates,
        request: Request,
        user: dict | None,
        current_app: str = "portal",
        app_nav: list[dict] | None = None,
        build_id: str = "",
        **extra: object,
    ) -> dict:
        """Return the context dict used by shell-based templates."""
        lang = self.language_service.detect(request)
        branches = AvaloneRegistry.for_shell(lang)
        sessions = self._session_context(request)
        auth_modal_html = self._auth_modal_context(request, templates, user)
        shell = Shell(
            current_app=current_app,
            user=user,
            sessions=sessions,
            auth_modal_html=auth_modal_html,
            branches=branches,
            app_nav=app_nav or [],
            lang=lang,
            portal_url=self.cfg.web_base_url,
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

    def _auth_modal_context(
        self, request: Request, templates: Jinja2Templates, user: dict | None
    ) -> str:
        mode = request.query_params.get("mode") or "login"
        if mode not in ("login", "register", "forgot", "reset"):
            mode = "login"
        token = request.query_params.get("token", "") if mode == "reset" else ""
        modal = AuthModal(mode=mode, token=token, user=user)
        return modal.render(templates.env, request)

    def _session_context(self, request: Request) -> list[dict]:
        uids = self.auth_service.session_uids(request)
        if not uids:
            return []
        active_uid = self.auth_service.active_user_id(request)
        sessions: list[dict] = []
        for uid in uids:
            u = self.user_service.get_user(uid)
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
    """Backward-compatible wrapper. Prefer injecting ``ShellContext``."""
    builder = ShellContext(
        auth_service=AuthService(),
        user_service=UserService(),
        language_service=LanguageService(),
        cfg=settings(),
    )
    return builder.build(
        templates,
        request,
        user,
        current_app=current_app,
        app_nav=app_nav,
        build_id=build_id,
        **extra,
    )
