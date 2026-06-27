"""API для реестра приложений и доступа текущего пользователя."""

from fastapi import APIRouter, Depends, HTTPException, status

from avalone_finance.core import app_access
from avalone_finance.web.api.dependencies import current_tenant, require_admin

router = APIRouter(prefix="/apps")


@router.get("")
async def apps_registry():
    """Публичный реестр всех приложений платформы."""
    return {"apps": app_access.registry()}


@router.get("/my")
async def my_apps(tenant_id: int = Depends(current_tenant)):
    """Список приложений, доступных текущему пользователю."""
    return {"apps": app_access.list_for_user(tenant_id)}
