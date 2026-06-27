"""Editor endpoints for categories and income sources.

Used by the 'More → Categories / Income sources' management screens.
"""
from fastapi import APIRouter

from avalone_finance.core import engine
from avalone_finance.web.api.common import _clabel, _is_visible

router = APIRouter(prefix="/edit")


@router.get("/categories")
async def edit_categories(lang: str = "ru"):
    """All expense categories for the editor (including disabled ones)."""
    accounts = await engine.list_accounts(include_disabled=True)
    items = [
        {"name": a["name"], "label": _clabel(a, lang), "disabled": bool(a.get("disabled"))}
        for a in accounts
        if a["root_type"] == "Expense" and _is_visible(a)
    ]
    return {"items": items}


@router.get("/incomes")
async def edit_incomes(lang: str = "ru"):
    """All income sources for the editor (including disabled ones)."""
    accounts = await engine.list_accounts(include_disabled=True)
    items = [
        {"name": a["name"], "label": _clabel(a, lang), "disabled": bool(a.get("disabled"))}
        for a in accounts
        if a["root_type"] == "Income" and _is_visible(a)
    ]
    return {"items": items}
