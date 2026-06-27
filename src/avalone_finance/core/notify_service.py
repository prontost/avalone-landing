"""Business logic for per-tenant settings and outbound e-mail.

Push notifications and weekly summaries were removed 2026-06-18. What remains:
- per-tenant settings (language, theme, layout, e-mail)
- a single outbound e-mail channel for password reset and verification codes.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from avalone_core.database import Service
from avalone_core import glossary_db as glossary
from avalone_finance.core.config import settings as cfg
from avalone_finance.core.notify_repository import NotifyRepository
from avalone_finance.core.tenant import TenantService

log = logging.getLogger(__name__)

DEFAULTS = {
    "email": "",
    "lang": "auto",      # auto | ru | en | ko; auto resolves in browser
    "theme": "auto",     # auto | light | dark
    # visibility/order of home widgets: "widget:1" visible, ":0" hidden
    "layout": "balances:1,journal:1",
}


class NotifyService(Service):
    """Per-tenant settings + e-mail sender."""

    def __init__(
        self,
        repository: NotifyRepository | None = None,
        tenant_service: TenantService | None = None,
    ) -> None:
        self._repo = repository or NotifyRepository()
        self._tenant = tenant_service or TenantService()

    def _tid(self) -> int:
        return self._tenant.require_current()

    def user_lang(self) -> str:
        return self.get_settings().get("lang", "ru")

    def get_settings(self) -> dict:
        rows = self._repo.get_settings(self._tid())
        return {**DEFAULTS, **rows}

    def set_settings(self, updates: dict) -> dict:
        allowed = set(DEFAULTS)
        filtered = {k: v for k, v in updates.items() if k in allowed}
        self._repo.set_settings(self._tid(), filtered)
        return self.get_settings()

    def send_email(self, to: str, title: str, body: str) -> bool:
        """Send a plain-text e-mail using configured SMTP credentials."""
        s = cfg()
        if not (s.smtp_host and s.smtp_user and s.smtp_password and to):
            return False
        from_addr = s.smtp_from or s.smtp_user
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = title
        # Sender name + correct Date/Message-ID/Reply-To reduce spam scores.
        msg["From"] = formataddr((glossary.t("app_name", lang="ru"), from_addr))
        msg["To"] = to
        msg["Reply-To"] = from_addr
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1])
        try:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
            return True
        except Exception:
            log.exception("email send failed")
            return False
