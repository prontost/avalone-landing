"""HTML page routes for the Avalone platform admin panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from avalone_core import glossary_db as glossary
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Button, Card, PageHeader
import avalone_core.ui
from avalone_landing.core.admin_service import AdminService
from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.web.dependencies import get_admin_service, require_permission
from avalone_landing.web.shell_context import render_shell_context

router = APIRouter()
BASE = Path(__file__).parent
_UI_DIR = Path(avalone_core.ui.__file__).parent
templates = Jinja2Templates(directory=[str(BASE / "templates"), str(_UI_DIR / "templates")])
templates.env.globals["t"] = glossary.t
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry

_ADMIN_NAV = [
    {
        "label": "",
        "entries": [
            {"label": glossary.t("admin_menu_dashboard"), "url": "/admin", "icon": "▣"},
            {"label": glossary.t("admin_menu_users"), "url": "/admin/users", "icon": "👤"},
            {"label": glossary.t("admin_menu_settings"), "url": "/admin/settings", "icon": "⚙"},
        ],
    }
]


def _admin_shell_context(
    request: Request,
    user: dict | None,
    active_path: str = "/admin",
    **extra: object,
) -> dict:
    from avalone_core.language_service import LanguageService

    lang = LanguageService().detect(request)
    nav = []
    for section in _ADMIN_NAV:
        entries = []
        for item in section["entries"]:
            entries.append({**item, "active": item["url"] == active_path})
        nav.append({"label": section["label"], "entries": entries})
    return render_shell_context(
        templates,
        request,
        user,
        current_app="portal",
        app_nav=nav,
        build_id=_ui_build_id(),
        lang=lang,
        **extra,
    )


def _ui_build_id() -> str:
    from avalone_core.ui import build_id as core_build_id

    return core_build_id()


def _user_dict(user) -> dict[str, Any]:
    return {
        "id": user.id,
        "login": user.login,
        "email": user.email,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "is_admin": user.is_admin,
        "roles": user.roles,
        "permissions": user.permissions,
        "module_counts": getattr(user, "module_counts", {}),
    }


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_permission("users:manage")),
):
    ctx = _admin_shell_context(request, {"id": admin.id, "login": admin.login}, active_path="/admin")
    ctx["user_count"] = admin_service._repo.count_users()
    ctx["admin_count"] = admin_service._repo.count_admins()
    module_counts = admin_service._repo.module_counts(admin.id)
    ctx["money_count"] = sum(c for t, c in module_counts.items() if t.startswith("money_"))
    ctx["header"] = PageHeader(title=glossary.t("admin_title")).render(templates.env, request)
    ctx["dashboard_card"] = Card(
        title=glossary.t("admin_title"),
        children=Markup("<p>{}</p>".format(glossary.t("admin_dashboard_welcome"))),
    ).render(templates.env, request)
    return templates.TemplateResponse(request, "admin/dashboard.html", ctx)


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    q: str = "",
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_permission("users:manage")),
):
    ctx = _admin_shell_context(request, {"id": admin.id, "login": admin.login}, active_path="/admin/users")
    users = admin_service.list_users()
    query = q.strip().lower()
    if query:
        users = [u for u in users if query in u.login.lower() or query in u.email.lower()]
    ctx["users"] = [_user_dict(u) for u in users]
    ctx["query"] = q
    ctx["all_roles"] = [r["name"] for r in RoleService().list_roles()]
    ctx["header"] = PageHeader(
        title=glossary.t("admin_users_title"),
        actions=[Button(label=glossary.t("admin_menu_settings"), href="/admin/settings", variant="secondary").render(templates.env, request)],
    ).render(templates.env, request)
    return templates.TemplateResponse(request, "admin/users.html", ctx)


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_permission("users:manage")),
):
    ctx = _admin_shell_context(request, {"id": admin.id, "login": admin.login}, active_path="/admin/users")
    user = admin_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ctx["target"] = _user_dict(user)
    ctx["all_roles"] = [r["name"] for r in RoleService().list_roles()]
    ctx["header"] = PageHeader(
        title=glossary.t("admin_user_detail_title"),
        actions=[Button(label=glossary.t("admin_users_title"), href="/admin/users", variant="secondary").render(templates.env, request)],
    ).render(templates.env, request)
    return templates.TemplateResponse(request, "admin/user_detail.html", ctx)


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_permission("server:settings")),
):
    ctx = _admin_shell_context(request, {"id": admin.id, "login": admin.login}, active_path="/admin/settings")
    ctx["settings"] = admin_service.list_server_settings()
    ctx["header"] = PageHeader(title=glossary.t("admin_settings_title")).render(templates.env, request)
    return templates.TemplateResponse(request, "admin/settings.html", ctx)
