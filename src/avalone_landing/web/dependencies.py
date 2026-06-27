"""FastAPI dependencies for the Avalone portal identity layer."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from avalone_landing.core.admin_service import AdminService
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.core.user_service import UserService


def get_user_service() -> UserService:
    return UserService()


def get_auth_service() -> AuthService:
    return AuthService()


def get_mail_service() -> MailService:
    return MailService()


def get_admin_service() -> AdminService:
    return AdminService()


async def current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> User | None:
    user_id = auth_service.user_id_of(request)
    if not user_id:
        return None
    return user_service.get_user(user_id)


def require_permission(permission: str):
    """Factory for a dependency that requires a specific RBAC permission."""
    async def checker(user: User = Depends(current_user)) -> User:
        if not user or not RoleService().has_permission(user.id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user
    return checker
