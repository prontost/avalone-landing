"""Shared shell rendering helper for Avalone portal pages."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from avalone_core.registry import AvaloneRegistry
from avalone_core.ui import Shell
import avalone_core.ui

_UI_DIR = Path(avalone_core.ui.__file__).parent
_UI_TEMPLATES_DIR = _UI_DIR / "templates"


def render_shell_context(
    templates: Jinja2Templates,
    request: Request,
    user: dict | None,
    current_app: str = "portal",
    app_nav: list[dict] | None = None,
    build_id: str = "",
    **extra: object,
) -> dict:
    """Return the context dict used by shell-based templates."""
    branches = AvaloneRegistry.for_shell("ru")
    shell = Shell(
        current_app=current_app,
        user=user,
        branches=branches,
        app_nav=app_nav or [],
        **extra,
    )
    return {
        "build_id": build_id,
        "user": user,
        "shell_html": shell.render(templates.env, request),
    }
