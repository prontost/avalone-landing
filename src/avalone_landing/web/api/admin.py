"""Admin JSON API for the Avalone portal platform administration panel."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from avalone_landing.core.admin_service import AdminService
from avalone_landing.core.models import User
from avalone_landing.web.dependencies import get_admin_service, require_admin

router = APIRouter(prefix="/api/admin")


class UpdateUserBody:
    def __init__(self, email: str | None = None, roles: list[str] | None = None) -> None:
        self.email = email
        self.roles = roles


class TransferBody:
    def __init__(self, to_user_id: int) -> None:
        self.to_user_id = to_user_id


class CopyBody:
    def __init__(self, to_user_id: int, tables: list[str]) -> None:
        self.to_user_id = to_user_id
        self.tables = tables


class SettingsBody:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings


class TestEmailBody:
    def __init__(self, to: str) -> None:
        self.to = to


def _user_to_dict(user) -> dict[str, Any]:
    return {
        "id": user.id,
        "login": user.login,
        "email": user.email,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "is_admin": user.is_admin,
        "roles": user.roles,
        "is_platform_admin": getattr(user, "is_platform_admin", False),
        "is_money_admin": getattr(user, "is_money_admin", False),
        "module_counts": getattr(user, "module_counts", {}),
    }


@router.get("/users")
async def list_users(
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    return {"users": [_user_to_dict(u) for u in admin_service.list_users()]}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    user = admin_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"user": _user_to_dict(user)}


@router.patch("/users/{user_id}")
async def update_user(
    request: Request,
    user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    user = admin_service.update_user(
        user_id,
        email=body.get("email"),
        roles=body.get("roles"),
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"user": _user_to_dict(user)}


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    temp: bool = Query(False),
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    url = admin_service.reset_password_link(user_id)
    result: dict[str, Any] = {"url": url}
    if temp:
        password = secrets.token_urlsafe(12)
        admin_service.set_temporary_password(user_id, password)
        result["temp_password"] = password
    return result


@router.post("/users/{user_id}/wipe-data")
async def wipe_data(
    user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    deleted = admin_service.wipe_user_data(user_id)
    return {"deleted": deleted}


@router.get("/users/{user_id}/export")
async def export_user_data(
    user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    data = admin_service.export_user_data(user_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=avalone-user-{user_id}.json"},
    )


@router.post("/users/{from_user_id}/transfer")
async def transfer_user_data(
    request: Request,
    from_user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    to_user_id = body.get("to_user_id")
    if not isinstance(to_user_id, int):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="to_user_id required")
    updated = admin_service.transfer_user_data(from_user_id, to_user_id)
    return {"updated": updated}


@router.post("/users/{from_user_id}/copy")
async def copy_user_data(
    request: Request,
    from_user_id: int,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    to_user_id = body.get("to_user_id")
    tables = body.get("tables", [])
    if not isinstance(to_user_id, int) or not isinstance(tables, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="to_user_id and tables required")
    copied = admin_service.copy_user_data(from_user_id, to_user_id, tables)
    return {"copied": copied}


@router.get("/settings")
async def list_settings(
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    return {"settings": admin_service.list_server_settings()}


@router.post("/settings")
async def update_settings(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    settings = body.get("settings", {})
    admin_service.update_server_settings(settings)
    return {"settings": admin_service.list_server_settings()}


@router.post("/settings/test-email")
async def test_email(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    to = body.get("to", "").strip()
    if not to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="to required")
    try:
        admin_service.send_test_email(to)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return {"ok": True}
