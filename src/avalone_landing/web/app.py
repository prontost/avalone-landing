"""Avalone landing page — catalog of apps under avalone.online."""

import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from avalone_core import glossary_db as glossary
from avalone_core.registry import AvaloneRegistry
import avalone_core.ui
from avalone_landing.config import settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.core.user_service import UserService
from avalone_landing.web.admin_router import router as admin_router
from avalone_landing.web.api.admin import router as admin_api_router
from avalone_landing.web.api.misc import router as misc_api_router
from avalone_landing.web.auth import router as auth_router
from avalone_landing.web.dependencies import current_user, get_shell_context
from avalone_landing.web.shell_context import ShellContext
from avalone_landing.web.work_router import router as work_router
from avalone_finance.web.app import finance_app

t = glossary.t


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from avalone_core.db import migrate as migrate_db

    migrate_db()
    _migrate_mail_settings()
    try:
        role_service = RoleService()
        role_service.ensure_defaults()
        user_service = UserService(role_service=role_service)
        if user_service.get_user(1):
            user_service.set_roles(1, ["owner"])
    except Exception:
        pass
    yield


app = FastAPI(title="avalone.online", lifespan=_lifespan)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(admin_api_router)
app.include_router(misc_api_router)
app.include_router(work_router)
app.mount("/finance", finance_app)
BASE = Path(__file__).parent
_templates_dir = BASE / "templates"
_static_dir = BASE / "static"
_ui_dir = Path(avalone_core.ui.__file__).parent
_ui_templates_dir = _ui_dir / "templates"
_ui_static_dir = _ui_dir / "static"
templates = Jinja2Templates(directory=[str(_templates_dir), str(_ui_templates_dir)])
templates.env.globals["t"] = glossary.t
templates.env.globals["td"] = glossary.td
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry
templates.env.globals["now"] = lambda: datetime.now(timezone.utc)


def _replace_query_param(query: object, key: str, value: object) -> str:
    params = dict(query) if hasattr(query, "__iter__") else {}
    params[key] = str(value)
    return "&".join(f"{k}={v}" for k, v in params.items())


templates.env.filters["replace_query_param"] = _replace_query_param
app.mount("/static/ui", StaticFiles(directory=str(_ui_static_dir)), name="ui_static")
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

_auth_service = AuthService()


@app.middleware("http")
async def current_user_ctx(request: Request, call_next):
    request.state.user_id = _auth_service.active_user_id(request)
    return await call_next(request)


def _build_id() -> str:
    h = hashlib.md5(usedforsecurity=False)
    for d in (_templates_dir, _static_dir, _ui_templates_dir, _ui_static_dir):
        for f in sorted(d.rglob("*")):
            if f.is_file():
                h.update(f"{f.name}:".encode())
                h.update(f.read_bytes())
    return h.hexdigest()[:12]


BUILD_ID = _build_id()


def _no_cache(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _render_shell(
    shell_context: ShellContext,
    request: Request,
    current_app: str = "portal",
    app_nav=None,
    **extra,
):
    return shell_context.build(
        templates,
        request,
        current_app=current_app,
        app_nav=app_nav or [],
        build_id=BUILD_ID,
        **extra,
    )


@app.get("/", response_class=HTMLResponse)
async def landing(
    request: Request,
    user: User | None = Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    ctx = _render_shell(shell_context, request, current_app="portal")
    ctx["branch_list"] = AvaloneRegistry.for_shell(ctx.get("lang", "ru"))
    return _no_cache(
        templates.TemplateResponse(
            request,
            "landing.html",
            ctx,
        )
    )


@app.get("/manifest.json")
async def manifest():
    return {
        "name": t("manifest_name"),
        "short_name": t("manifest_short_name"),
        "description": t("manifest_description"),
        "start_url": "/?source=pwa",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0a0c10",
        "theme_color": "#0a0c10",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "categories": ["productivity", "utilities", "lifestyle"],
        "lang": "ru",
    }


def _migrate_mail_settings() -> None:
    """Move SMTP/mail settings from legacy module tables to avalone_global_settings."""
    from avalone_core.repositories import SettingsRepository

    keys = (
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_use_tls",
        "mail_from",
        "mail_from_name",
    )
    SettingsRepository().migrate_from_legacy(keys, source_table="money_global_settings")


@app.get("/icon.svg")
async def icon():
    return FileResponse(_static_dir / "icon.svg", media_type="image/svg+xml")


@app.get("/icon-192.png")
async def icon_192():
    return FileResponse(_static_dir / "icon-192.png", media_type="image/png")


@app.get("/icon-512.png")
async def icon_512():
    return FileResponse(_static_dir / "icon-512.png", media_type="image/png")


@app.get("/sw.js")
async def sw():
    return _no_cache(
        FileResponse(_static_dir / "sw.js", media_type="application/javascript")
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/version")
async def version():
    return {"build": BUILD_ID}


@app.get("/api/apps")
async def apps_catalog():
    return {
        "apps": [
            {
                "id": b.id,
                "name_key": b.name_key,
                "icon": b.icon,
                "description_key": b.description_key,
                "status": b.status,
                "url": b.url,
                "module": b.module,
            }
            for b in AvaloneRegistry.active()
        ]
    }
