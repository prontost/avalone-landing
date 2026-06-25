"""Avalone landing page — catalog of apps under avalone.online."""

import hashlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from avalone_landing.config import APPS, BRANCHES, settings
from avalone_landing.core import users
from avalone_landing.web.auth import SESSION_COOKIE, _signer, router as auth_router

app = FastAPI(title="avalone.online")
app.include_router(auth_router)
BASE = Path(__file__).parent
_templates_dir = BASE / "templates"
_static_dir = BASE / "static"
templates = Jinja2Templates(directory=str(_templates_dir))


@app.middleware("http")
async def current_user_ctx(request: Request, call_next):
    token = request.cookies.get(SESSION_COOKIE)
    user_id = 0
    if token:
        try:
            user_id = int(_signer.loads(token))
        except Exception:
            user_id = 0
    users.set_current(user_id)
    return await call_next(request)


def _build_id() -> str:
    h = hashlib.md5(usedforsecurity=False)
    for f in sorted((_templates_dir).rglob("*")):
        if f.is_file():
            h.update(f"{f.name}:".encode())
            h.update(f.read_bytes())
    for f in sorted((_static_dir).rglob("*")):
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


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user = users.get_user(users.current())
    return _no_cache(
        templates.TemplateResponse(
            request,
            "landing.html",
            {"apps": APPS, "branches": BRANCHES, "build_id": BUILD_ID, "user": user},
        )
    )


@app.get("/manifest.json")
async def manifest():
    return {
        "name": "Avalone",
        "short_name": "Avalone",
        "description": "Цифровая вселенная поверх реального мира.",
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
    return {"apps": APPS}
