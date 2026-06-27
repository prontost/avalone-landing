"""Counta API domain router."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from avalone_core import glossary_db as glossary
from avalone_finance.core import constants, engine, entry_meta, lexicon, money
from avalone_finance.web.api.common import (
    _clabel, _human_label, _label, _lex_chat,
)

log = logging.getLogger(__name__)
router = APIRouter()

_SORTS = {
    "occurred_desc": "posting_date desc, name desc",
    "occurred_asc": "posting_date asc, name asc",
    "created_desc": "creation desc",
    "created_asc": "creation asc",
    "amount_desc": "total_debit desc",
    "amount_asc": "total_debit asc",
}

_TEST_NOISE = ("contract-test", "pwa e2e", "кпз e2e", "пробная")

_MISC_MARKERS = ("прочее", "other", "разобрать")


def _is_misc(account_name: str) -> bool:
    return any(m in account_name.lower() for m in _MISC_MARKERS)


@router.post("/entry")
async def post_entry(payload: dict):
    """Hard input path: explicit accounts chosen in the UI. Deterministic."""
    try:
        amount = Decimal(str(payload["amount"]))
        if amount <= 0:
            raise InvalidOperation
    except (KeyError, InvalidOperation, ValueError):
        return JSONResponse({"error": "error_amount_positive"}, status_code=400)
    op = payload.get("op", "expense")
    debit, credit = payload.get("debit"), payload.get("credit")
    accounts = await engine.list_accounts()
    acc_map = {a["name"]: a for a in accounts}
    if debit not in acc_map or credit not in acc_map:
        return JSONResponse({"error": "error_unknown_account"}, status_code=400)
    remark = (payload.get("remark") or "").strip() or _human_label(debit, acc_map[debit])
    # Дата возникновения транзакции (не путать с моментом внесения записи):
    # пользователь может указать когда транзакция реально произошла. По умолчанию
    # — сейчас. Дата → posting_date (нативно в ERPNext), полное время → entry_meta.
    occurred = entry_meta.parse_occurred(payload.get("occurred_at")) or datetime.now()
    name = await engine.post_journal_entry(
        occurred.date(), remark, debit, credit, amount)
    entry_meta.set_occurred(name, occurred.isoformat(timespec="minutes"))
    # форма = подтверждённый выбор пользователя -> учим лексикон бесплатно
    if payload.get("learn_phrase"):
        kind = "category" if op == "expense" else "money"
        lexicon.save(_lex_chat(), kind, payload["learn_phrase"], debit if op == "expense" else credit)
    debit_label = _human_label(debit, acc_map[debit])
    credit_label = _human_label(credit, acc_map[credit])
    cur = (payload.get("currency") or "").strip()
    amt = f"{amount:,.0f} {cur}".strip()
    lang = payload.get("lang", "ru")
    if op == "expense":
        summary = f"{remark} — {amt} · {glossary.t('rv_from', lang=lang)} «{credit_label}»"
    elif op == "income":
        summary = f"{remark} — {amt} · {glossary.t('rv_to', lang=lang)} «{debit_label}»"
    else:
        summary = f"{remark} — {amt} · {credit_label} → {debit_label}"
    return {"id": name, "summary": summary}

@router.post("/entry/{entry_id}/cancel")
async def cancel_entry(entry_id: str):
    await engine.cancel_journal_entry(entry_id)
    return {"ok": True}

@router.post("/entry/{entry_id}/recategorize")
async def recategorize(entry_id: str, payload: dict):
    """Разбор: перенести запись в нормальную категорию (сторно + новая)."""
    new_debit = payload.get("debit")
    accounts = await engine.list_accounts()
    acc_map = {a["name"]: a for a in accounts}
    if new_debit not in acc_map:
        return JSONResponse({"error": "error_unknown_account"}, status_code=400)
    rows = await engine.recent_entries(limit=constants.get("recent_entries_limit"))
    old = next((r for r in rows if r["name"] == entry_id), None)
    if old is None:
        return JSONResponse({"error": "error_entry_not_found"}, status_code=404)
    accs = await engine.entry_accounts(entry_id)
    if not accs:
        return JSONResponse({"error": "error_entry_read_failed"}, status_code=500)
    await engine.cancel_journal_entry(entry_id)
    new_id = await engine.post_journal_entry(
        old["posting_date"] if isinstance(old["posting_date"], date)
        else date.fromisoformat(str(old["posting_date"])),
        old["user_remark"] or _human_label(new_debit, acc_map[new_debit]),
        new_debit, accs[1], Decimal(str(old["total_debit"])))
    # сохраняем точное время возникновения исходной транзакции на новой проводке
    prev_occ = entry_meta.occurred_map([entry_id]).get(entry_id)
    if prev_occ:
        entry_meta.set_occurred(new_id, prev_occ)
    if payload.get("learn_phrase"):
        lexicon.save(_lex_chat(), "category", payload["learn_phrase"], new_debit)
    return {"id": new_id, "summary": f"→ {_human_label(new_debit, acc_map[new_debit])}"}

@router.post("/entry/{entry_id}/restore")
async def restore_entry(entry_id: str):
    """Вернуть отменённую проводку (docstatus 2 необратим → создаём копию).
    Отменённые показываются прямо в журнале блёкло; возврат — оттуда инлайн."""
    new_id = await engine.restore_entry(entry_id)
    prev_occ = entry_meta.occurred_map([entry_id]).get(entry_id)
    if prev_occ:
        entry_meta.set_occurred(new_id, prev_occ)
    return {"id": new_id}

@router.post("/entry/{entry_id}/purge")
async def purge_entry(entry_id: str):
    """Удалить проводку НАВСЕГДА (физически, без призраков). Доступно из журнала
    для отменённых записей. Метаданные тоже чистим."""
    try:
        await engine.delete_entry(entry_id)
        entry_meta.forget(entry_id)
    except engine.EngineError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}

@router.get("/balances")
async def balances(lang: str = "ru"):
    """Остатки ПОВАЛЮТНО: счета каждой валюты суммируются отдельно, общего
    смешанного итога нет (валюты не складываем). Список валютных групп строится
    динамически из того, что реально в реестре/БД — без хардкода.

    Долг/актив — по ЗНАКУ фактического баланса (+ = деньги есть, − = должен),
    а не по типу счёта: овердрафт обычного счёта показывается долгом, как кредитка."""
    accounts = [a for a in await engine.list_accounts()
                if a["root_type"] in ("Asset", "Liability")]
    bals = await asyncio.gather(*(engine.account_balance(a["name"]) for a in accounts))
    reg_cur = money.registered_full()
    # сгруппировать по валюте счёта (из нашего реестра; вне реестра → DEFAULT)
    groups: dict[str, dict] = {}
    for a, b in zip(accounts, bals):
        bf = float(b)
        if not bf:
            continue
        cur = reg_cur.get(a["name"], {}).get("currency", money.DEFAULT_CURRENCY)
        g = groups.setdefault(cur, {"currency": cur, "items": [],
                                    "assets": 0.0, "debts": 0.0})
        item = {"label": _clabel(a, lang), "amount": abs(bf), "debt": bf < 0}
        g["items"].append(item)
        (g.__setitem__("debts", g["debts"] + item["amount"]) if item["debt"]
         else g.__setitem__("assets", g["assets"] + item["amount"]))
    out = []
    for cur, g in sorted(groups.items()):
        g["net"] = g["assets"] - g["debts"]
        out.append(g)
    return {"groups": out}

@router.get("/entries")
async def entries(limit: int = 20, offset: int = 0, lang: str = "ru",
                  category: str | None = None, only: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  created_from: str | None = None, created_to: str | None = None,
                  amount_min: str | None = None, amount_max: str | None = None,
                  account: str | None = None, q: str | None = None,
                  currency: str | None = None, op_type: str | None = None,
                  income: str | None = None,
                  sort: str = "occurred_desc", hide_cancelled: str | None = None):
    """Журнал с фильтрами + пагинация (offset/limit, has_more для автодогрузки):
    - category=<account name>: только проводки с этим счётом в дебете (расход);
    - income=<account name>: только проводки с этим счётом в кредите (источник дохода);
    - op_type=expense|income|transfer: фильтр по типу операции;
    - only=uncategorized: только черновые/«Прочее» (висящие на разбор);
    - date_from/date_to: диапазон даты возникновения (posting_date);
    - created_from/created_to: диапазон даты внесения записи (creation);
    - amount_min/amount_max: диапазон суммы;
    - sort: occurred|created|amount × asc|desc.
    Когда фильтр активен, выбираем из большего окна, чтобы не «терять» старое."""
    extra: list = []
    if date_from:    extra.append(["posting_date", ">=", date_from])
    if date_to:      extra.append(["posting_date", "<=", date_to])
    if created_from: extra.append(["creation", ">=", created_from])
    if created_to:   extra.append(["creation", "<=", created_to + " 23:59:59"])
    if amount_min:
        try: extra.append(["total_debit", ">=", float(amount_min)])
        except ValueError: pass
    if amount_max:
        try: extra.append(["total_debit", "<=", float(amount_max)])
        except ValueError: pass
    order = _SORTS.get(sort, _SORTS["occurred_desc"])
    # тянем окно с запасом под offset+limit (и шире при пост-фактум фильтре по
    # category/only). Не «все от начала времён» — растёт по мере прокрутки.
    need = offset + limit
    post_filter = category or only or account or q or currency or op_type or income
    fetch_n = max(need, 500) if post_filter else need + limit
    q_low = q.strip().lower() if q else None
    # docstatus (1,2): проведённые + отменённые — отменённые показываем в журнале
    # блёкло инлайн (а не в отдельной «корзине»).
    # hide_cancelled=1 — фильтруем отменённые уже в ERPNext, чтобы пагинация
    # не поехала от выпадения строк.
    statuses = (1,) if hide_cancelled == "1" else (1, 2)
    rows = await engine.recent_entries(limit=fetch_n, extra_filters=extra,
                                        order_by=order, docstatus=statuses)
    # include disabled accounts so their labels still render for old entries
    accs_map = {a["name"]: a for a in await engine.list_accounts(include_disabled=True)}
    accs_all = await asyncio.gather(*(engine.entry_accounts(r["name"]) for r in rows))
    reg_cur = money.registered_full()   # {pk: {currency...}} — валюта денежного счёта

    def _entry_currency(accs):
        # валюта записи = валюта денежного счёта в проводке (любой из сторон)
        for a in (accs or []):
            if a in reg_cur:
                return reg_cur[a]["currency"]
        return money.DEFAULT_CURRENCY

    def _entry_op(debit_rt: str | None, credit_rt: str | None) -> str:
        if debit_rt == "Expense":
            return "expense"
        if credit_rt == "Income":
            return "income"
        if debit_rt == "Asset" and credit_rt == "Asset":
            return "transfer"
        return "expense"  # fallback for legacy/unusual shapes

    matched = []
    for r, accs in zip(rows, accs_all):
        debit, credit = accs if accs else (None, None)
        debit_rt = accs_map.get(debit, {}).get("root_type") if debit else None
        credit_rt = accs_map.get(credit, {}).get("root_type") if credit else None
        op = _entry_op(debit_rt, credit_rt)
        if category and debit != category:
            continue
        if income and credit != income:
            continue
        if only == "uncategorized" and not (debit and _is_misc(_label(debit))):
            continue
        # account: счёт участвует в проводке с ЛЮБОЙ стороны (дебет или кредит)
        if account and account not in (accs or []):
            continue
        if currency and _entry_currency(accs) != currency:
            continue
        if op_type:
            if op_type == "expense" and not (debit_rt == "Expense"):
                continue
            if op_type == "income" and not (credit_rt == "Income"):
                continue
            if op_type == "transfer" and not (debit_rt == "Asset" and credit_rt == "Asset"):
                continue
        if q_low and q_low not in (r.get("user_remark") or "").lower():
            continue
        # отменённый dev-мусор не показываем в реальном журнале
        if r.get("docstatus") == 2 and any(
                n in (r.get("user_remark") or "").lower() for n in _TEST_NOISE):
            continue
        matched.append((r, accs, debit, credit, op))
    page = matched[offset:offset + limit]
    occ = entry_meta.occurred_map([r["name"] for r, _, _, _, _ in page])

    def _disp(pk):
        # имя счёта в журнале: пользовательское имя денежного счёта (переименование)
        # -> catalog -> сырое. Ключ pk стабилен, имя берётся «на лету».
        custom = money.account_label(pk)
        if custom:
            return custom
        a = accs_map.get(pk)
        return _clabel(a, lang) if a else _label(pk)

    out = [{"id": r["name"], "date": str(r["posting_date"]),
            # точное время возникновения (если задано) и момент внесения записи
            "occurred_at": occ.get(r["name"]) or str(r["posting_date"]),
            "created": str(r.get("creation") or ""),
            "cancelled": r.get("docstatus") == 2,   # отменённая → блёкло + кнопка возврата
            "amount": float(r["total_debit"]),
            "currency": _entry_currency(accs),
            "remark": r["user_remark"] or r["name"],
            "op": op,
            "to_name": debit or "",
            "to": _disp(debit) if accs else "",
            "from_name": credit or "",
            "from": _disp(credit) if accs else ""}
           for r, accs, debit, credit, op in page]
    has_more = len(matched) > offset + limit
    return {"entries": out, "has_more": has_more}


def _period_range(period: str, date_from: str | None = None, date_to: str | None = None):
    """(date_from, date_to, label_key) для отчёта. Локаль времени — Asia/Seoul."""
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    if period == "custom" and date_from and date_to:
        return date_from, date_to, "rep_custom"
    if period == "prev_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1).isoformat(), last_prev.isoformat(), "rep_prev_month"
    if period == "year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat(), "rep_year"
    if period == "all":
        return None, None, "rep_all"
    if period == "week":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday.isoformat(), sunday.isoformat(), "rep_week"
    if period == "prev_week":
        monday = today - timedelta(days=today.weekday() + 7)
        sunday = monday + timedelta(days=6)
        return monday.isoformat(), sunday.isoformat(), "rep_prev_week"
    if period == "last7":
        return (today - timedelta(days=6)).isoformat(), today.isoformat(), "rep_last7"
    if period == "last30":
        return (today - timedelta(days=29)).isoformat(), today.isoformat(), "rep_last30"
    if period == "last90":
        return (today - timedelta(days=89)).isoformat(), today.isoformat(), "rep_last90"
    return today.replace(day=1).isoformat(), today.isoformat(), "rep_month"


async def _report_groups(period: str, lang: str, date_from: str | None = None, date_to: str | None = None):
    """Ядро отчёта: вернуть (date_from, date_to, label_key, groups)."""
    date_from, date_to, label_key = _period_range(period, date_from, date_to)
    extra: list = []
    if date_from:
        extra.append(["posting_date", ">=", date_from])
    if date_to:
        extra.append(["posting_date", "<=", date_to])
    accounts = await engine.list_accounts()
    root_of = {a["name"]: a["root_type"] for a in accounts}
    reg_cur = money.registered_full()

    def _cur(accs):
        for a in (accs or []):
            if a in reg_cur:
                return reg_cur[a]["currency"]
        return money.DEFAULT_CURRENCY

    rows = await engine.recent_entries(
        limit=constants.get("export_entries_limit"), extra_filters=extra, docstatus=(1,)
    )
    accs_all = await asyncio.gather(*(engine.entry_accounts(r["name"]) for r in rows))
    cur_data: dict = {}

    def _g(c):
        return cur_data.setdefault(
            c,
            {
                "currency": c,
                "income": 0.0,
                "expense": 0.0,
                "n": 0,
                "_exp": {},
                "_inc": {},
            },
        )

    for r, accs in zip(rows, accs_all):
        if not accs:
            continue
        debit, credit = accs[0], (accs[1] if len(accs) > 1 else None)
        amt = abs(float(r["total_debit"]))
        if not amt:
            continue
        c = _cur(accs)
        if root_of.get(debit) == "Expense":
            g = _g(c)
            g["expense"] += amt
            g["n"] += 1
            g["_exp"][debit] = g["_exp"].get(debit, 0.0) + amt
        elif credit and root_of.get(credit) == "Income":
            g = _g(c)
            g["income"] += amt
            g["n"] += 1
            g["_inc"][credit] = g["_inc"].get(credit, 0.0) + amt

    def _disp(pk):
        custom = money.account_label(pk)
        if custom:
            return custom
        a = next((x for x in accounts if x["name"] == pk), None)
        return _clabel(a, lang) if a else _label(pk)

    out = []
    for c, g in sorted(cur_data.items()):
        exp_items = sorted(g["_exp"].items(), key=lambda kv: -kv[1])
        inc_items = sorted(g["_inc"].items(), key=lambda kv: -kv[1])
        exp_total = g["expense"] or 1.0
        out.append(
            {
                "currency": c,
                "income": round(g["income"]),
                "expense": round(g["expense"]),
                "net": round(g["income"] - g["expense"]),
                "count": g["n"],
                "top_expenses": [
                    {"key": k, "label": _disp(k), "amount": round(v), "pct": round(v / exp_total * 100)}
                    for k, v in exp_items[:8]
                ],
                "incomes": [{"key": k, "label": _disp(k), "amount": round(v)} for k, v in inc_items[:8]],
            }
        )
    return date_from, date_to, label_key, out


@router.get("/report")
async def report(period: str = "month", lang: str = "ru",
                 date_from: str | None = None, date_to: str | None = None):
    """Детерминированный отчёт за период (без LLM): доход/расход/итог ПОВАЛЮТНО,
    топ категорий расхода и доход по источникам. Переводы между своими счетами
    в доход/расход не попадают."""
    date_from, date_to, label_key, groups = await _report_groups(
        period, lang, date_from, date_to)
    return {"period": period, "label_key": label_key,
            "date_from": date_from, "date_to": date_to, "groups": groups}
