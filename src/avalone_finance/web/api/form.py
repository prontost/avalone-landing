"""Avalone Finance API domain router."""

import asyncio
import logging

from fastapi import APIRouter, Depends

from avalone_finance.core import glossary, ledger_ops
from avalone_finance.core.catalog_service import CatalogService
from avalone_finance.core.currency_service import CurrencyService
from avalone_finance.core.ledger_service import LedgerService
from avalone_finance.core.money_account_service import MoneyAccountService
from avalone_finance.web.api.common import (
    _clabel, _is_visible, _money_label,
)
from avalone_finance.web.api.dependencies import (
    get_catalog_service,
    get_currency_service,
    get_ledger_service,
    get_money_account_service,
)

log = logging.getLogger(__name__)
router = APIRouter()

# «Свалки»-холдинги: в дроплисте ввода НЕ показываются (старые остатки на
# «Прочее»/«Разобрать»), но в фильтре журнала «без категории» выделяются.
# «Укажу позже» (Uncategorized) — дефолт формы, показывается как обычная.
_MISC_MARKERS = ("прочее", "other", "разобрать")


def _is_misc(account_name: str) -> bool:
    return any(m in account_name.lower() for m in _MISC_MARKERS)


@router.get("/form-data")
async def form_data(
    lang: str = "ru",
    include_disabled: bool = False,
    ledger_service: LedgerService = Depends(get_ledger_service),
    money_service: MoneyAccountService = Depends(get_money_account_service),
    catalog_service: CatalogService = Depends(get_catalog_service),
    currency_service: CurrencyService = Depends(get_currency_service),
):
    """Everything the entry form needs: categories + money accounts.
    include_disabled=true — показать скрытые счета/категории (для правки старых
    записей или переноса остатков), они помечаются флагом disabled."""
    accounts = ledger_service.list_accounts(include_disabled=include_disabled)
    cats = [a for a in accounts
            if a["root_type"] == "Expense"
            and a.get("account_type") not in ledger_ops._EXCLUDED_ACCOUNT_TYPES
            and (not _is_misc(a["account_name"]) or a["account_name"] in ("Uncategorized", "Other expense"))
            and _is_visible(a)]
    cat_names = [a["name"] for a in cats]
    bals = [ledger_service.account_balance(a["name"]) for a in cats]
    counts = ledger_service.entry_counts(cat_names)
    used, rest = [], []
    for a, b in zip(cats, bals):
        item = {"name": a["name"], "label": _clabel(a, lang),
                "is_uncategorized": a["account_name"] == "Uncategorized",
                "count": counts.get(a["name"], 0),
                "disabled": bool(a.get("disabled")),
                "role": catalog_service.role(a["account_name"])}
        is_user = catalog_service.is_user_category(a["name"]) and a["account_name"] not in catalog_service.CANON
        (used if (float(b) or is_user) else rest).append(item)
    # used: сначала по частоте убыв., затем по роли/алфавиту; rest: по роли/алфавиту
    role_order = {"need": 0, "want": 1, "goal": 2, "": 9}
    used.sort(key=lambda x: (-x["count"], role_order.get(x["role"], 9), x["label"].lower()))
    rest.sort(key=lambda x: (role_order.get(x["role"], 9), x["label"].lower()))
    # «Укажу позже» (Uncategorized) — всегда закреплена первой в дроплисте,
    # независимо от частоты: это дефолт быстрого ввода «разберу потом».
    pinned = [x for x in used + rest if x["is_uncategorized"]]
    if pinned:
        used = pinned + [x for x in used if not x["is_uncategorized"]]
        rest = [x for x in rest if not x["is_uncategorized"]]
    # money-счета: локализуем через catalog (Наличные→Cash→현금 если есть перевод),
    # иначе показываем имя как назвал пользователь (банки — его собственные ярлыки).
    # currency — валюта счёта (наш реестр), форма подставит её в дроплист валют.
    label_of = {a["name"]: a for a in accounts}
    money_list = [{"name": name, "label": _money_label(name, raw, lang),
                   "currency": money_service.account_currency(name),
                   "disabled": bool(label_of.get(name, {}).get("disabled"))}
                  for raw, name in ledger_ops.money_options(accounts)]
    incomes = [{"name": a["name"], "label": _clabel(a, lang),
                "disabled": bool(a.get("disabled"))}
               for a in accounts if a["root_type"] == "Income"
               and _is_visible(a)
               and a.get("account_type") not in ledger_ops._EXCLUDED_ACCOUNT_TYPES]
    # долги (debt) удалены из формы — вернём по новой схеме учёта позже.
    return {"categories_used": used, "categories_all": rest,
            "money": money_list, "incomes": incomes,
            "currencies": currency_service.options(lang)}


@router.get("/glossary")
async def glossary_all(full: int = 0):
    """Единый глоссарий — источник истины. full=0: {ru:{...},en,ko} для фронта.
    full=1: полные строки [{key,ru,en,ko,kind,desc}] — для редактора/ИИ-перевода
    (desc = контекст, без которого ИИ переведёт строку наугад)."""
    if full:
        return {"entries": glossary.entries(), "missing_desc": glossary.missing_desc()}
    return glossary.all_by_lang()


@router.post("/glossary/seed")
async def glossary_seed(payload: dict):
    """Однократный посев глоссария из встроенного фронт-словаря (bootstrap).
    Идемпотентно: перезаписывает ключи. payload = {ru:{key:txt}, en:{...}, ko:{...}}."""
    by_lang = payload or {}
    keys = set()
    for lng in glossary.LANGS:
        keys |= set((by_lang.get(lng) or {}).keys())
    rows = [{"key": k,
             "ru": (by_lang.get("ru") or {}).get(k, ""),
             "en": (by_lang.get("en") or {}).get(k, ""),
             "ko": (by_lang.get("ko") or {}).get(k, ""),
             "kind": "ui"} for k in sorted(keys)]
    n = glossary.upsert_many(rows)
    # проставить метаописания UI-ключам (контекст для ИИ-перевода)
    from avalone_finance.core import ui_glossary
    described = ui_glossary.apply_descriptions()
    return {"seeded": n, "described": described}


@router.get("/currencies")
async def currencies(
    lang: str = "ru",
    currency_service: CurrencyService = Depends(get_currency_service),
):
    """Список валют для дроплистов: фиат + крипта (тогл на фронте)."""
    return currency_service.options(lang)


@router.get("/convert")
async def convert(
    amount: float,
    frm: str,
    to: str,
    currency_service: CurrencyService = Depends(get_currency_service),
):
    """Живой курс без кэша: перевести amount из валюты frm в to.
    {value: float} или {value: null} если курс недоступен (форма не подставит)."""
    val = await currency_service.convert(amount, frm, to)
    return {"value": val, "from": frm.upper(), "to": to.upper()}
