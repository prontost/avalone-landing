"""FastAPI dependencies shared by API routers."""

from fastapi import Depends, HTTPException, Request, status

from avalone_core import glossary_db as glossary
from avalone_finance.core import tenant
from avalone_finance.core.app_access_service import AppAccessService
from avalone_finance.core.global_settings_service import GlobalSettingsService
from avalone_finance.core.notification_service import NotificationService
from avalone_finance.core.notify_service import NotifyService
from avalone_finance.core.tenant import TenantService


def current_tenant() -> int:
    """Return the tenant_id set by the auth middleware."""
    return tenant.require_current()


# alias for routes that need any authenticated user
require_user = current_tenant


def get_user_service() -> TenantService:
    """Factory for the request-scoped tenant/user service."""
    return TenantService()


def get_global_settings_service() -> GlobalSettingsService:
    """Factory for the instance-wide global settings service."""
    return GlobalSettingsService()


def get_app_access_service() -> AppAccessService:
    """Factory for the per-user app access service."""
    return AppAccessService()


def get_notification_service() -> NotificationService:
    """Factory for the per-tenant notification log service."""
    return NotificationService()


def get_notify_service() -> NotifyService:
    """Factory for the per-tenant settings/e-mail service."""
    return NotifyService()


def require_admin(
    request: Request,
    user_service: TenantService = Depends(get_user_service),
) -> int:
    """Ensure the current tenant is an instance admin."""
    tid = user_service.require_current()
    if not user_service.is_admin(tid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=glossary.t("error_forbidden", lang="ru"),
        )
    return tid
