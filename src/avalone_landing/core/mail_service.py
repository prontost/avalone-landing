"""Outbound mail service for the Avalone portal."""

from __future__ import annotations

import smtplib
import subprocess
from email.message import EmailMessage
from ssl import create_default_context
from typing import Any

from avalone_core.database import Service

from avalone_landing.config import Settings, settings


class MailService(Service):
    """Send plain-text email via SMTP relay or local sendmail fallback."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or settings()

    def send_email(self, to: str, subject: str, body: str) -> None:
        """Send a plain-text email. Raises on failure."""
        self.send_email_with_config(to, subject, body, cfg=self._cfg.model_dump())

    def send_email_with_config(
        self,
        to: str,
        subject: str,
        body: str,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        """Send a plain-text email using the supplied config or process defaults."""
        cfg = cfg or self._cfg.model_dump()
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{cfg.get('mail_from_name', 'Avalone')} <{cfg.get('mail_from', 'noreply@avalone.online')}>"
        msg["To"] = to
        msg.set_content(body)

        smtp_host = cfg.get("smtp_host", "")
        if smtp_host:
            self._send_smtp_dict(cfg, msg)
        else:
            self._send_sendmail_dict(cfg, msg)

    def _send_smtp_dict(self, cfg: dict[str, Any], msg: EmailMessage) -> None:
        smtp_host = cfg["smtp_host"]
        smtp_port = int(cfg.get("smtp_port", 587))
        smtp_user = cfg.get("smtp_user", "")
        smtp_password = cfg.get("smtp_password", "")
        use_tls = str(cfg.get("smtp_use_tls", "true")).lower() not in ("", "0", "false", "no", "off")
        context = create_default_context()
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls(context=context)
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)

    def _send_sendmail_dict(self, cfg: dict[str, Any], msg: EmailMessage) -> None:
        mail_from = cfg.get("mail_from", "noreply@avalone.online")
        payload = msg.as_bytes()
        result = subprocess.run(
            ["sendmail", "-t", "-f", mail_from],
            input=payload,
            capture_output=True,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"sendmail failed ({result.returncode}): {err}")

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
