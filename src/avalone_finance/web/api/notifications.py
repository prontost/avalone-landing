"""API для журнала уведомлений пользователя."""

from fastapi import APIRouter, Depends, HTTPException, status

from avalone_core import glossary_db as glossary
from avalone_finance.core.notification_service import NotificationService
from avalone_finance.web.api.dependencies import current_tenant, get_notification_service

router = APIRouter(prefix="/notifications")


@router.get("")
async def list_notifications(
    app: str = "money",
    filter: str = "all",
    limit: int = 50,
    offset: int = 0,
    tenant_id: int = Depends(current_tenant),
    service: NotificationService = Depends(get_notification_service),
):
    """Список уведомлений текущего пользователя для приложения app.

    filter: all | unread | read | dismissed
    """
    if filter not in ("all", "unread", "read", "dismissed"):
        filter = "all"
    return service.list_(tenant_id, app, filter=filter, limit=limit, offset=offset)


@router.post("/read")
async def mark_read(
    payload: dict,
    tenant_id: int = Depends(current_tenant),
    service: NotificationService = Depends(get_notification_service),
):
    ids = [int(i) for i in payload.get("ids", []) if str(i).isdigit()]
    n = service.mark_read(ids, tenant_id)
    return {"marked": n}


@router.post("/dismiss")
async def mark_dismissed(
    payload: dict,
    tenant_id: int = Depends(current_tenant),
    service: NotificationService = Depends(get_notification_service),
):
    ids = [int(i) for i in payload.get("ids", []) if str(i).isdigit()]
    n = service.mark_dismissed(ids, tenant_id)
    return {"dismissed": n}


@router.get("/unread-count")
async def unread_count(
    app: str = "money",
    tenant_id: int = Depends(current_tenant),
    service: NotificationService = Depends(get_notification_service),
):
    return {"count": service.count_unread(tenant_id, app)}


@router.post("")
async def create_notification(
    payload: dict,
    tenant_id: int = Depends(current_tenant),
    service: NotificationService = Depends(get_notification_service),
):
    """Ручное создание уведомления (для тестов и системных событий)."""
    title = payload.get("title", "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=glossary.t("error_empty_name", lang="ru"),
        )
    nid = service.add(
        tenant_id,
        app=payload.get("app", "money"),
        title=title,
        body=payload.get("body", ""),
        kind=payload.get("kind", "info"),
    )
    return {"id": nid}
