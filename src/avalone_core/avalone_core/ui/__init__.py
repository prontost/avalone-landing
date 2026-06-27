"""Shared Avalone UI widgets and templates."""
import hashlib
from pathlib import Path

from avalone_core.ui.widgets import (
    Widget,
    Shell,
    SearchOverlay,
    AppSwitcher,
    ProfileMenu,
    BottomNav,
    NavSidebar,
    Card,
    Button,
    PageHeader,
    Alert,
)

__all__ = [
    "Widget",
    "Shell",
    "SearchOverlay",
    "AppSwitcher",
    "ProfileMenu",
    "BottomNav",
    "NavSidebar",
    "Card",
    "Button",
    "PageHeader",
    "Alert",
    "build_id",
]


def build_id(hash_length: int = 12) -> str:
    """Hash of all UI templates and static files for cache busting."""
    h = hashlib.md5(usedforsecurity=False)
    root = Path(__file__).parent
    for sub in ("templates", "static"):
        for f in sorted((root / sub).rglob("*")):
            if f.is_file():
                h.update(f"{f.relative_to(root)}:".encode())
                h.update(f.read_bytes())
    return h.hexdigest()[:hash_length]
