"""FastAPI dependencies for the Avalone portal identity layer."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_service import UserService


def get_user_service() -> UserService:
    return UserService()


def get_auth_service() -> AuthService:
    return AuthService()


def get_mail_service() -> MailService:
    return MailService()


async def current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> User | None:
    user_id = auth_service.user_id_of(request)
    if not user_id:
        return None
    return user_service.get_user(user_id)


async def require_admin(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> User:
    user_id = auth_service.user_id_of(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    user = user_service.get_user(user_id)
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return user
