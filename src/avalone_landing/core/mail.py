"""Minimal outbound mail helper for Avalone portal.

Thin backward-compatible facade over MailService.
"""

from __future__ import annotations

from avalone_landing.core.mail_service import MailService

_default_service = MailService()

send_email = _default_service.send_email
