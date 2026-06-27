"""Журнал уведомлений пользователя в разрезе приложений.

Каждое уведомление привязано к пользователю (tenant_id) и к приложению (app).
Таблица в единой БД — `money_notifications`; Counta добавляет свои колонки
`app`, `read_at`, `dismissed_at`, если их ещё нет.

Backward-compatible facade: module-level functions delegate to the default
NotificationService instance.
"""

from avalone_finance.core.notification_repository import NotificationRepository
from avalone_finance.core.notification_service import NotificationService

# --- backward-compatible module-level API ---
_default_service = NotificationService()

add = _default_service.add
list_ = _default_service.list_
mark_read = _default_service.mark_read
mark_dismissed = _default_service.mark_dismissed
count_unread = _default_service.count_unread

__all__ = [
    "NotificationRepository",
    "NotificationService",
    "add",
    "list_",
    "mark_read",
    "mark_dismissed",
    "count_unread",
]
