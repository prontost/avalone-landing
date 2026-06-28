"""Avalone Finance API domain router."""

import logging

from fastapi import APIRouter, Depends

from avalone_finance.core.config import settings as cfg
from avalone_finance.core.notify_service import NotifyService
from avalone_finance.web.api.dependencies import get_notify_service

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings(service: NotifyService = Depends(get_notify_service)):
    s = service.get_settings()
    s["email_channel_ready"] = bool(cfg().smtp_user and cfg().smtp_password)
    return s


@router.post("/settings")
async def set_settings(
    payload: dict,
    service: NotifyService = Depends(get_notify_service),
):
    return service.set_settings(payload)
