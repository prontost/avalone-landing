"""Управление доступом пользователей к приложениям платформы avalone.online.

Реестр приложений (KNOWN_APPS) живёт в коде: новое приложение добавляется
сюда, и админ может включить/выключить доступ конкретным пользователям.
По умолчанию публичные приложения (public=True) доступны всем; отключение
записывается в money_user_apps и скрывает приложение из переключателя.

Таблица money_user_apps ссылается на users с ON DELETE CASCADE, но из-за того, что
SQLite по умолчанию не включает foreign_keys, tenant.delete_user явно чистит
money_user_apps (и notifications) вместе с пользователем.

Backward-compatible facade: module-level functions delegate to the default
AppAccessService instance.
"""

from avalone_finance.core.app_access_repository import AppAccessRepository
from avalone_finance.core.app_access_service import (
    AppAccessService,
    KNOWN_APPS,
)

# --- backward-compatible module-level API ---
_default_service = AppAccessService()

registry = _default_service.registry
list_for_user = _default_service.list_for_user
is_accessible = _default_service.is_accessible
list_for_admin = _default_service.list_for_admin
set_access = _default_service.set_access
grant_default = _default_service.grant_default
delete_for_user = _default_service.delete_for_user

__all__ = [
    "KNOWN_APPS",
    "AppAccessRepository",
    "AppAccessService",
    "registry",
    "list_for_user",
    "is_accessible",
    "list_for_admin",
    "set_access",
    "grant_default",
    "delete_for_user",
]
