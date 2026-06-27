"""Counta API routers aggregator.

Domain routers are registered here under the /api prefix. External code should
import `router` from this package (e.g. `from avalone_finance.web.api import router`).
"""

from fastapi import APIRouter

from avalone_finance.web.api import (
    accounts,
    admin,
    analytics,
    app_access,
    edit,
    entries,
    form,
    misc,
    notifications,
    settings,
)
from avalone_finance.web.api.common import (
    _clabel,
    _human_label,
    _is_visible,
    _label,
    _lex_chat,
    _money_label,
)

router = APIRouter(prefix="/api")

router.include_router(form.router)
router.include_router(accounts.router)
router.include_router(entries.router)
router.include_router(settings.router)
router.include_router(analytics.router, prefix="/analytics")
router.include_router(edit.router)
router.include_router(admin.router)
router.include_router(misc.router)
router.include_router(notifications.router)
router.include_router(app_access.router)

__all__ = [
    "router",
    "_lex_chat",
    "_label",
    "_clabel",
    "_money_label",
    "_human_label",
    "_is_visible",
]
