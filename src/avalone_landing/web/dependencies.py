"""FastAPI dependencies for the Avalone portal identity layer."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from avalone_core.device_service import DeviceService
from avalone_core.language_service import LanguageService
from avalone_core.referral_service import ReferralService
from avalone_landing.config import settings
from avalone_landing.core.admin_service import AdminService
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.feedback_service import FeedbackService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.core.user_service import UserService
from avalone_landing.web.auth_controller import AuthController
from avalone_landing.web.shell_context import ShellContext


def get_role_service() -> RoleService:
    return RoleService()


def get_user_service() -> UserService:
    role_service = get_role_service()
    return UserService(role_service=role_service)


def get_auth_service() -> AuthService:
    return AuthService()


def get_mail_service() -> MailService:
    return MailService()


def get_auth_controller(
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
    mail_service: MailService = Depends(get_mail_service),
) -> AuthController:
    return AuthController(auth_service, user_service, mail_service, settings())


def get_admin_service() -> AdminService:
    role_service = get_role_service()
    return AdminService(role_service=role_service)


def get_feedback_service() -> FeedbackService:
    return FeedbackService()


def get_shell_context(
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> ShellContext:
    return ShellContext(
        auth_service=auth_service,
        user_service=user_service,
        language_service=get_language_service(),
        cfg=settings(),
    )


def get_device_service() -> DeviceService:
    return DeviceService()


def get_referral_service() -> ReferralService:
    return ReferralService()


def get_language_service() -> LanguageService:
    return LanguageService()


async def current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service),
) -> User | None:
    user_id = auth_service.active_user_id(request)
    if not user_id:
        return None
    return user_service.get_user(user_id)


def require_permission(permission: str):
    """Factory for a dependency that requires a specific RBAC permission."""
    async def checker(
        user: User = Depends(current_user),
        role_service: RoleService = Depends(get_role_service),
    ) -> User:
        if not user or not role_service.has_permission(user.id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user
    return checker
