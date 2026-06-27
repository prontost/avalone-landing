"""User settings (SQLite) + outbound e-mail channel.

Push-уведомления и недельный итог удалены 2026-06-18 (нечего слать). Остались:
- money_user_settings (per-tenant): язык, раскладка главной, e-mail.
- send_email: единственный исходящий канал — нужен для восстановления
  логина/пароля по почте и кодов подтверждения (security.py).

Backward-compatible facade: module-level functions delegate to the default
NotifyService instance.
"""

from avalone_finance.core.notify_repository import NotifyRepository
from avalone_finance.core.notify_service import DEFAULTS, NotifyService

# --- backward-compatible module-level API ---
_default_service = NotifyService()

user_lang = _default_service.user_lang
get_settings = _default_service.get_settings
set_settings = _default_service.set_settings
send_email = _default_service.send_email
_send_email = _default_service.send_email

__all__ = [
    "DEFAULTS",
    "NotifyRepository",
    "NotifyService",
    "user_lang",
    "get_settings",
    "set_settings",
    "send_email",
    "_send_email",
]
