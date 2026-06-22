"""Avalone landing page — catalog of apps under avalone.online."""

import hashlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from avalone_landing.config import APPS, settings

app = FastAPI(title="avalone.online")
BASE = Path(__file__).parent
_templates_dir = BASE / "templates"
_static_dir = BASE / "static"
templates = Jinja2Templates(directory=str(_templates_dir))


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
    return _no_cache(
        templates.TemplateResponse(
            request,
            "landing.html",
            {"apps": APPS, "build_id": BUILD_ID},
        )
    )


@app.get("/manifest.json")
async def manifest():
    return {
        "name": "avalone.online",
        "short_name": "avalone",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f1115",
        "theme_color": "#0f1115",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }


@app.get("/icon.svg")
async def icon():
    return FileResponse(_static_dir / "icon.svg", media_type="image/svg+xml")


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
