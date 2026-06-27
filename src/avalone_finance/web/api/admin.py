"""Admin / instance management endpoints."""

import asyncio
import logging
import os
import signal
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from avalone_core import glossary_db as glossary
from avalone_finance.core import constants, currency, db
from avalone_finance.core.app_access_service import AppAccessService
from avalone_finance.core.config import settings
from avalone_finance.core.global_settings_service import GlobalSettingsService
from avalone_finance.core.money import DEFAULT_CURRENCY
from avalone_finance.core.tenant import OWNER_TENANT_ID, TenantService
from avalone_finance.web.api.dependencies import (
    get_app_access_service,
    get_global_settings_service,
    get_user_service,
    require_admin,
)


def _t(key: str) -> str:
    """Admin dashboard is Russian-only for now; translate glossary key."""
    return glossary.t(key, lang="ru")


def _build_id() -> str:
    """Lazy import to avoid a circular import with web.app."""
    from avalone_finance.web.app import BUILD_ID

    return BUILD_ID


log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")


@router.get("/settings")
async def admin_settings(
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: current global settings like registration mode."""
    del admin_id
    runtime = global_settings_service.get_runtime()
    return {
        "registration_mode": runtime["registration_mode"],
        "registration_invite_code": runtime["registration_invite_code"],
        "strict_password_policy": runtime["strict_password_policy"],
    }


@router.post("/settings")
async def admin_settings_update(
    payload: dict,
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: update global settings."""
    del admin_id
    allowed = {"registration_mode", "registration_invite_code", "strict_password_policy"}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "registration_mode" and value not in ("open", "invite", "closed"):
            return JSONResponse({"error": _t("error_invalid_mode")}, status_code=400)
        if key == "strict_password_policy":
            value = "true" if str(value).strip().lower() in ("1", "true", "yes", "on") else "false"
        global_settings_service.set(key, str(value))
    runtime = global_settings_service.get_runtime()
    return {
        "registration_mode": runtime["registration_mode"],
        "registration_invite_code": runtime["registration_invite_code"],
        "strict_password_policy": runtime["strict_password_policy"],
    }


@router.get("/users")
async def admin_users(
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
    app_access_service: AppAccessService = Depends(get_app_access_service),
):
    """Admins: list all users with entry counts and app access."""
    del admin_id
    users = user_service.list_users()
    return {
        "users": [
            {
                **u,
                "email_verified": False,
                "apps": app_access_service.list_for_admin(u["id"]),
            }
            for u in users
        ]
    }


@router.get("/stats")
async def admin_stats(
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
):
    """Admins: instance-wide stats."""
    del admin_id
    db_size = db.DB_PATH.stat().st_size if db.DB_PATH.exists() else 0
    return {
        "build_id": _build_id(),
        "db_path": str(db.DB_PATH),
        "db_size": db_size,
        "users": user_service.count_users(),
        "entries": user_service.count_entries(),
        "currencies": len(currency.ALL),
    }


@router.get("/health")
async def admin_health(
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: basic health checks."""
    del admin_id
    db_ok = False
    try:
        global_settings_service.get_all()
        db_ok = True
    except Exception:
        log.exception("admin health db check failed")
    return {"db_ok": db_ok, "db_path": str(db.DB_PATH)}


@router.get("/admins")
async def admin_list(
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
):
    """Admins: list current admins."""
    del admin_id
    return {"admins": user_service.list_admins()}


@router.get("/constants")
async def admin_constants_list(admin_id: int = Depends(require_admin)):
    """Admins: all tunable constants with current values and defaults."""
    del admin_id
    return {
        "constants": [
            {"key": k, "value": constants.get(k), "default": v, "type": type(v).__name__}
            for k, v in constants.DEFAULTS.items()
        ],
    }


@router.post("/constants")
async def admin_constants_update(
    payload: dict,
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: update one or more tunable constants."""
    del admin_id
    updates = payload.get("updates", {})
    for key, value in updates.items():
        if key not in constants.DEFAULTS:
            return JSONResponse(
                {"error": _t("error_unknown_constant").replace("{key}", key)},
                status_code=400,
            )
        default = constants.DEFAULTS[key]
        try:
            if isinstance(default, bool):
                str(value).lower() in ("1", "true", "yes", "on")
            elif isinstance(default, int):
                int(value)
            elif isinstance(default, float):
                float(value)
            elif isinstance(default, Decimal):
                Decimal(value)
        except Exception:
            return JSONResponse(
                {"error": _t("error_invalid_value").replace("{key}", key)},
                status_code=400,
            )
        global_settings_service.set(key, str(value))
    return {"ok": True, "constants": constants.all_effective()}


@router.post("/admins")
async def admin_add(
    payload: dict,
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
):
    """Admins: add a user as admin by login."""
    del admin_id
    login = (payload.get("login") or "").strip().lower()
    u = user_service.get_user_by_login(login)
    if not u:
        return JSONResponse({"error": _t("error_user_not_found")}, status_code=404)
    user_service.add_admin(u["id"])
    return {"ok": True, "id": u["id"], "login": u["login"]}


@router.delete("/admins/{user_id}")
async def admin_remove(
    user_id: int,
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
):
    """Admins: remove admin rights."""
    del admin_id
    user_service.remove_admin(user_id)
    return {"ok": True}


@router.get("/config")
async def admin_config(
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: editable runtime config + env secrets (masked) + static constants."""
    del admin_id
    runtime = global_settings_service.get_runtime()
    s = settings()

    def _mask(v: str | None) -> str:
        v = v or ""
        if len(v) <= 4:
            return "*" * len(v) or "—"
        return v[:2] + "****" + v[-2:]

    return {
        "runtime": runtime,
        "static": {
            "OWNER_TENANT_ID": OWNER_TENANT_ID,
            "DEFAULT_CURRENCY": DEFAULT_CURRENCY,
            "registration_mode_env": s.registration_mode,
            "registration_invite_code_env": bool(s.registration_invite_code),
            "currencies_count": len(currency.ALL),
        },
        "env": {
            "smtp_password": _mask(s.smtp_password),
            "fernet_key": _mask(s.fernet_key),
            "web_host": s.web_host,
            "web_port": s.web_port,
            "smtp_host": s.smtp_host,
            "smtp_port": s.smtp_port,
            "smtp_user": s.smtp_user,
            "smtp_from": s.smtp_from,
        },
        "options": {
            "currencies": sorted(currency.ALL.keys()),
            "registration_modes": ["open", "invite", "closed"],
            "default_currencies": sorted(currency.ALL.keys()),
        },
    }


@router.post("/config")
async def admin_config_update(
    payload: dict,
    admin_id: int = Depends(require_admin),
    global_settings_service: GlobalSettingsService = Depends(get_global_settings_service),
):
    """Admins: update runtime config keys stored in global_settings."""
    del admin_id
    allowed = {
        "registration_mode",
        "registration_invite_code",
        "strict_password_policy",
        "default_currency",
        "web_base_url",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "registration_mode" and value not in ("open", "invite", "closed"):
            return JSONResponse({"error": _t("error_invalid_mode")}, status_code=400)
        if key == "default_currency" and value not in currency.ALL:
            return JSONResponse({"error": _t("error_unknown_currency")}, status_code=400)
        if key == "strict_password_policy":
            value = "true" if str(value).strip().lower() in ("1", "true", "yes", "on") else "false"
        global_settings_service.set(key, str(value))
    return {"ok": True, **global_settings_service.get_runtime()}


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    admin_id: int = Depends(require_admin),
    user_service: TenantService = Depends(get_user_service),
):
    """Admins: delete user and all their data."""
    if user_id == admin_id:
        return JSONResponse({"error": _t("error_cannot_delete_self")}, status_code=400)
    admins = user_service.list_admins()
    if any(a["id"] == user_id for a in admins) and len(admins) <= 1:
        return JSONResponse({"error": _t("error_last_admin")}, status_code=400)
    u = user_service.get_user(user_id)
    if not u:
        return JSONResponse({"error": _t("error_user_not_found")}, status_code=404)
    user_service.delete_user(user_id)
    return {"ok": True}


@router.get("/user-apps")
async def admin_user_apps(
    user_id: int,
    admin_id: int = Depends(require_admin),
    app_access_service: AppAccessService = Depends(get_app_access_service),
):
    """Admins: per-user app access state for the toggles."""
    del admin_id
    return {"user_id": user_id, "apps": app_access_service.list_for_admin(user_id)}


@router.post("/user-apps")
async def admin_set_user_app(
    payload: dict,
    admin_id: int = Depends(require_admin),
    app_access_service: AppAccessService = Depends(get_app_access_service),
):
    """Admins: enable/disable a specific app for a user."""
    del admin_id
    user_id = payload.get("user_id")
    app_id = (payload.get("app_id") or "").strip()
    enabled = bool(payload.get("enabled"))
    if not isinstance(user_id, int) or not app_id:
        return JSONResponse({"error": _t("error_user_app_required")}, status_code=400)
    try:
        app_access_service.set_access(user_id, app_id, enabled)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


@router.get("/logs")
async def admin_logs(lines: int = 200, admin_id: int = Depends(require_admin)):
    """Admins: tail of application log file."""
    del admin_id
    log_path = (db.DB_PATH.parent if db.DB_PATH else Path.home() / ".counta") / "counta.log"
    if not log_path.exists():
        return {"lines": [], "path": str(log_path)}
    lines = max(1, min(int(lines), 2000))
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        tail = f.readlines()[-lines:]
    return {"lines": tail, "path": str(log_path)}


@router.post("/restart")
async def admin_restart(admin_id: int = Depends(require_admin)):
    """Admins: ask the process to exit; launchd will restart it."""
    del admin_id

    async def _do_restart():
        await asyncio.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_do_restart())
    return {"ok": True, "message": "restarting"}
