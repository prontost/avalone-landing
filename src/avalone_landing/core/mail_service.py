"""Outbound mail service for the Avalone portal."""

from __future__ import annotations

import smtplib
import subprocess
from email.message import EmailMessage
from ssl import create_default_context

from avalone_core.database import Service

from avalone_landing.config import Settings, settings


class MailService(Service):
    """Send plain-text email via SMTP relay or local sendmail fallback."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or settings()

    def send_email(self, to: str, subject: str, body: str) -> None:
        """Send a plain-text email. Raises on failure."""
        cfg = self._cfg
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{cfg.mail_from_name} <{cfg.mail_from}>"
        msg["To"] = to
        msg.set_content(body)

        if cfg.smtp_host:
            self._send_smtp(cfg, msg)
        else:
            self._send_sendmail(cfg, msg)

    def _send_smtp(self, cfg: Settings, msg: EmailMessage) -> None:
        context = create_default_context()
        if cfg.smtp_use_tls:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.starttls(context=context)
                if cfg.smtp_user:
                    server.login(cfg.smtp_user, cfg.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                if cfg.smtp_user:
                    server.login(cfg.smtp_user, cfg.smtp_password)
                server.send_message(msg)

    def _send_sendmail(self, cfg: Settings, msg: EmailMessage) -> None:
        payload = msg.as_bytes()
        result = subprocess.run(
            ["sendmail", "-t", "-f", cfg.mail_from],
            input=payload,
            capture_output=True,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"sendmail failed ({result.returncode}): {err}")
