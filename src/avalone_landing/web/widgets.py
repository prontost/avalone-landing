"""Avalone landing-specific widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from avalone_core.ui.widgets import Widget


@dataclass
class AuthModal(Widget):
    """Modal with login / register / forgot-password / reset-password views."""

    template_name: str = "widgets/auth_modal.html"
    mode: str = "login"
    token: str = ""
    user: Any = None

    def context(self, request: Any = None) -> dict:
        ctx = super().context(request)
        ctx["request"] = request
        ctx["user"] = self.user
        ctx["mode"] = self.mode
        ctx["token"] = self.token
        return ctx
