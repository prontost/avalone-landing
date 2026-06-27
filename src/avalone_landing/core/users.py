"""Avalone users and password auth.

Thin backward-compatible facade over the class-based identity layer.
New code should use UserService / UserRepository directly.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone

from avalone_landing.core.models import User
from avalone_landing.core.role_service import RoleService
from avalone_landing.core.user_repository import UserRepository
from avalone_landing.core.user_service import UserService

_current: ContextVar[int] = ContextVar("user_id", default=0)

_default_repo = UserRepository()
_default_service = UserService(_default_repo)


# --- request context ---

def set_current(user_id: int) -> None:
    _current.set(user_id)


def current() -> int:
    return _current.get()


def require_current() -> int:
    uid = _current.get()
    if not uid:
        raise PermissionError("user not authenticated")
    return uid


# --- password helpers ---

hash_password = _default_repo.hash_password
verify_password = _default_repo.verify_password


# --- user lookup ---

def _user_to_dict(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "login": user.login,
        "email": user.email,
        "created_at": user.created_at,
    }


def get_by_login(login: str) -> dict | None:
    login = login.strip().lower()
    with _default_repo._conn() as con:
        row = con.execute(
            "SELECT id, login, pwhash, email, created_at FROM users WHERE login = ?",
            (login,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "login": row["login"],
        "pwhash": row["pwhash"],
        "email": row["email"] or "",
        "created_at": row["created_at"],
    }


def get_user(user_id: int) -> dict | None:
    return _user_to_dict(_default_service.get_user(user_id))


def authenticate(login: str, password: str) -> int | None:
    user = _default_service.authenticate(login, password)
    return user.id if user else None


def login_taken(login: str) -> bool:
    return _default_service.login_taken(login)


def create_user(login: str, password: str, email: str = "") -> int:
    return _default_service.create_user(login, password, email)


# --- password changes ---

def change_password(user_id: int, current_password: str, new_password: str) -> bool:
    return _default_service.change_password(user_id, current_password, new_password)


# --- password reset tokens ---

def set_reset_token(login_or_email: str) -> tuple[int, str] | None:
    result = _default_service.request_password_reset(login_or_email)
    if result is None:
        return None
    user, token = result
    return user.id, token


def get_by_reset_token(token: str) -> dict | None:
    user = _default_repo.get_by_reset_token(token)
    if user is None:
        return None
    return {
        "id": user.id,
        "login": user.login,
        "email": user.email,
    }


def reset_password(user_id: int, new_password: str) -> None:
    _default_repo.set_password_hash(user_id, _default_repo.hash_password(new_password))
    _default_repo.clear_reset_token(user_id)


# --- admin helpers (role-based) ---

def is_admin(user_id: int | None) -> bool:
    return _default_service.has_permission(user_id, "users:manage")


def list_admins() -> list[dict]:
    return [
        _user_to_dict(u) for u in _default_service.list_users()
        if u and ("admin:full" in u.permissions or "users:manage" in u.permissions)
    ]


def add_admin(user_id: int) -> None:
    current = set(_default_service.get_roles(user_id))
    current.add("admin")
    _default_service.set_roles(user_id, list(current))


def remove_admin(user_id: int) -> None:
    current = [r for r in _default_service.get_roles(user_id) if r != "admin"]
    _default_service.set_roles(user_id, current)
