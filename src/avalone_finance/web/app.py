"""Avalone Finance — formerly Counta. Hard input forms, deterministic outputs.

Telegram retired (разворот №3). Auth: Avalone SSO via shared signed cookie.
No AI/LLM layer: all analytics and tips are rule-based.

Mounted inside the avalone.online portal app under /finance.
"""

import hashlib
import logging
import logging.handlers
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from avalone_core import glossary_db as glossary
from avalone_core.language_service import LanguageService
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Shell, build_id as ui_build_id
import avalone_core.ui
from avalone_finance.core import constants, db, external_auth, security, tenant
from avalone_finance.core.config import settings
from avalone_finance.core.glossary_seed import seed as _seed_glossary
from avalone_finance.web.api import router as api_router


def _setup_logging() -> None:
    """Пишем логи приложения в файл с ротацией; stderr оставляем для launchd."""
    log_dir = db.DB_PATH.parent if db.DB_PATH else Path.home() / ".counta"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "counta.log",
        maxBytes=constants.get("log_max_bytes"),
        backupCount=constants.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)


_setup_logging()

finance_app = FastAPI(title="Avalone Finance", root_path="/finance")
BASE = Path(__file__).parent
_templates_dir = BASE / "templates"
_static_dir = BASE / "static"
_ui_dir = Path(avalone_core.ui.__file__).parent
_ui_templates_dir = _ui_dir / "templates"
_ui_static_dir = _ui_dir / "static"
templates = Jinja2Templates(directory=[str(_templates_dir), str(_ui_templates_dir)])
templates.env.globals["t"] = glossary.t
templates.env.globals["i18n_js"] = glossary.i18n_js
templates.env.globals["registry"] = AvaloneRegistry
# Shared UI static files are served by the portal app at /static/ui.
finance_app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def _build_id() -> str:
    """Хеш UI-изменений: при любом изменении шаблонов/статики/веб-API клиенты
    получают новый build и принудительно перезагружаются."""
    h = hashlib.md5(usedforsecurity=False)
    root = BASE.parent  # src/avalone_finance
    for sub in ["web", "templates", "static"]:
        p = root / sub
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                try:
                    h.update(f"{f.relative_to(root)}:".encode())
                    h.update(f.read_bytes())
                except Exception:
                    pass
    # shared UI
    for sub in ("templates", "static"):
        p = _ui_dir / sub
        for f in sorted(p.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                try:
                    h.update(f"ui/{sub}/{f.name}:".encode())
                    h.update(f.read_bytes())
                except Exception:
                    pass
    return h.hexdigest()[:constants.get("build_id_hash_length")]


BUILD_ID = _build_id()


def _relative_path(request: Request) -> str:
    """Return the path inside the finance sub-app (strip /finance root_path)."""
    root_path = request.scope.get("root_path", "")
    path = request.scope.get("path", "")
    if root_path and path.startswith(root_path):
        return path[len(root_path):] or "/"
    return path


@finance_app.middleware("http")
async def auth_gate(request: Request, call_next):
    open_paths = {
        "/admin/login", "/admin",
        "/manifest.json", "/sw.js", "/healthz",
        "/icon.svg", "/icon-192.png", "/icon-512.png",
        "/api/version", "/api/apps", "/qr"
    }
    path = _relative_path(request)
    tid = external_auth.user_id_of(request)
    # КАЖДЫЙ запрос ставит текущего тенанта в contextvar — все запросы к БД
    # фильтруются по нему (изоляция данных между пользователями).
    tenant.set_current(tid)
    if path not in open_paths and not path.startswith("/static/") and not tid:
        if path.startswith("/api"):
            return JSONResponse({"error": glossary.t("error_unauthorized", lang="ru")}, status_code=401)
        return RedirectResponse(_avalone_login_url(request), status_code=303)
    response = await call_next(request)
    return response


def _avalone_login_url(request: Request) -> str:
    next_url = str(request.url)
    return f"{settings().avalone_base_url}/login?next={next_url}"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


@finance_app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    # Finance no longer manages its own sessions; use the portal login.
    return RedirectResponse(
        f"{settings().avalone_base_url}/login?next={settings().avalone_base_url}/finance/admin",
        status_code=303,
    )


@finance_app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    avalone_uid = external_auth.user_id_of(request)
    if not avalone_uid or not tenant.is_admin(avalone_uid):
        return RedirectResponse("/finance/admin/login", status_code=303)
    lang = LanguageService(auth_service=external_auth).detect(request)
    return _no_cache(templates.TemplateResponse(request, "admin_dashboard.html", {
        "build_id": BUILD_ID,
        "user": tenant.get_user(avalone_uid),
        "lang": lang,
        "i18n": glossary.all_by_lang(module="money"),
    }))


def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _shell_context_for(request: Request, user, current_app: str = "money"):
    lang = LanguageService(auth_service=external_auth).detect(request)
    branches = AvaloneRegistry.for_shell(lang)
    shell = Shell(current_app=current_app, user=user, branches=branches, app_nav=[], lang=lang)
    return {
        "build_id": BUILD_ID,
        "user": user,
        "lang": lang,
        "shell_html": shell.render(templates.env, request),
    }


@finance_app.get("/", response_class=HTMLResponse)
async def app_page(request: Request):
    user = tenant.get_user(tenant.current()) if tenant.current() else None
    ctx = _shell_context_for(request, user, current_app="money")
    return _no_cache(templates.TemplateResponse(request, "app.html", ctx))


@finance_app.get("/manifest.json")
async def manifest():
    return _no_cache(JSONResponse({
        "name": glossary.t("manifest_name_money", lang="ru"),
        "short_name": glossary.t("manifest_short_name_money", lang="ru"),
        "description": glossary.t("manifest_description_money", lang="ru"),
        "start_url": "/finance/", "display": "standalone",
        "background_color": "#0a0c10", "theme_color": "#0a0c10",
        "icons": [
            {"src": f"/finance/icon-192.png?v={BUILD_ID}", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": f"/finance/icon-512.png?v={BUILD_ID}", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": f"/finance/icon.svg?v={BUILD_ID}", "sizes": "any", "type": "image/svg+xml"},
        ],
    }))


@finance_app.get("/icon.svg")
async def icon():
    return _no_cache(FileResponse(BASE / "static" / "icon.svg", media_type="image/svg+xml"))


@finance_app.get("/icon-192.png")
async def icon_192():
    return _no_cache(FileResponse(BASE / "static" / "icon-192.png", media_type="image/png"))


@finance_app.get("/icon-512.png")
async def icon_512():
    return _no_cache(FileResponse(BASE / "static" / "icon-512.png", media_type="image/png"))


@finance_app.get("/qr")
async def qr(url: str = "", size: int = constants.get("qr_default_size")):
    """SVG QR-код для быстрого входа/регистрации."""
    if not url:
        url = settings().web_base_url or "/finance/"
    try:
        import qrcode
        import qrcode.image.svg
        factory = qrcode.image.svg.SvgFragmentImage
        qr = qrcode.QRCode(image_factory=factory, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf)
        svg = buf.getvalue()
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@finance_app.get("/sw.js")
async def sw():
    return _no_cache(FileResponse(BASE / "static" / "sw.js", media_type="application/javascript"))


@finance_app.get("/logout")
async def logout():
    # Portal auth owns the session; redirect to portal logout.
    return RedirectResponse(f"{settings().avalone_base_url}/logout", status_code=303)


@finance_app.get("/healthz")
async def healthz():
    return {"ok": True}


@finance_app.get("/api/version")
async def version():
    return {"build": BUILD_ID}


finance_app.include_router(api_router)


@finance_app.on_event("startup")
async def _ensure_catalog():
    """Идемпотентно гарантируем базовый набор категорий с переводами ru/en/ko —
    чтобы новый пользователь не смотрел в пустой дроплист (см. catalog.DEFAULT_KEYS).
    Сид выполняется для всех существующих тенантов (никакого служебного owner)."""
    _setup_logging()  # uvicorn перезаписывает root-логгер, поэтому ставим handler ещё раз
    import logging
    from avalone_finance.core import catalog, money
    # Ensure unified glossary keys exist before any page renders.
    try:
        _seed_glossary()
    except Exception:
        logging.getLogger(__name__).exception("glossary seed")
    for tid in tenant.all_ids():
        tenant.set_current(tid)
        try:
            n = await catalog.ensure_user_catalog()
            if n:
                logging.getLogger(__name__).info("ensure_user_catalog tenant=%s: created %d categories", tid, n)
        except Exception:
            logging.getLogger(__name__).exception("ensure_user_catalog tenant=%s", tid)
        try:
            m = await money.ensure_money_seed()
            if m:
                logging.getLogger(__name__).info("ensure_money_seed tenant=%s: seeded %d money accounts", tid, m)
        except Exception:
            logging.getLogger(__name__).exception("ensure_money_seed tenant=%s", tid)
    # этапы B/A глоссария: доменные строки — в единый глоссарий
    # (уведомления, валюты, канонические категории/доходы под нейтральными ключами)
    try:
        from avalone_finance.core import currency
        currency.seed_glossary()
        catalog.seed_glossary()
    except Exception:
        logging.getLogger(__name__).exception("glossary domain seed")
    # Гарантируем наличие ролей по умолчанию и хотя бы одного администратора Counta.
    try:
        from avalone_landing.core.role_service import RoleService, RoleRepository
        RoleService(RoleRepository(tenant._default_repo._db)).ensure_defaults()
        if not tenant.list_admins():
            admin_login = "lucifer"
            u = tenant.get_user_by_login(admin_login)
            if u:
                tenant.add_admin(u["id"])
                logging.getLogger(__name__).info(
                    "created default admin: %s (uid=%s)", admin_login, u["id"])
    except Exception:
        logging.getLogger(__name__).exception("ensure default admin")
