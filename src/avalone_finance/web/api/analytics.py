"""Analytics domain router: reports, tips, charts data."""

import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from avalone_finance.core import constants, engine, money, tips
from avalone_finance.web.api.dependencies import require_user
from avalone_finance.web.api.entries import _period_range, _report_groups

router = APIRouter()


async def _debt_summary() -> list[dict]:
    """Current outstanding debts and net worth per currency.

    Debt = absolute value of negative balances on Asset/Liability accounts.
    """
    accounts = [a for a in await engine.list_accounts(include_disabled=False)
                if a["root_type"] in ("Asset", "Liability")]
    bals = await asyncio.gather(*(engine.account_balance(a["name"]) for a in accounts))
    reg_cur = money.registered_full()
    groups: dict[str, dict] = {}
    for a, b in zip(accounts, bals):
        bf = float(b)
        if not bf:
            continue
        cur = reg_cur.get(a["name"], {}).get("currency", money.DEFAULT_CURRENCY)
        g = groups.setdefault(cur, {"currency": cur, "assets": 0.0, "debts": 0.0})
        if bf < 0:
            g["debts"] += abs(bf)
        else:
            g["assets"] += bf
    out = []
    for cur, g in sorted(groups.items()):
        out.append({
            "currency": cur,
            "assets": round(g["assets"]),
            "debts": round(g["debts"]),
            "net": round(g["assets"] - g["debts"]),
        })
    return out


@router.get("/summary")
async def analytics_summary(period: str = "month", lang: str = "ru",
                            date_from: str | None = None, date_to: str | None = None,
                            user_id: int = Depends(require_user)):
    """Same data as /api/report plus current debt snapshot."""
    date_from, date_to, label_key, groups = await _report_groups(
        period, lang, date_from, date_to)
    debts = await _debt_summary()
    return {"period": period, "label_key": label_key,
            "date_from": date_from, "date_to": date_to, "groups": groups,
            "debts": debts}


@router.get("/tip")
async def analytics_tip(period: str = "month", lang: str = "ru",
                        user_id: int = Depends(require_user)):
    """Personalized tip based on current-period report and outstanding debts."""
    try:
        _, _, _, groups = await _report_groups(period, lang)
        debts = await _debt_summary()
        total_debt = sum(d["debts"] for d in debts)
        return tips.select_tip(groups, lang, total_debt=total_debt)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/tips")
async def analytics_tips_library(lang: str = "ru", user_id: int = Depends(require_user)):
    """Library of all financial-literacy tips."""
    return {"tips": tips.all_tips(lang)}


@router.get("/trend")
async def analytics_trend(period: str = "month", group_by: str = "day",
                          lang: str = "ru", user_id: int = Depends(require_user)):
    """Time-series income/expense/net for the selected period.

    group_by: day | week | month
    """
    date_from, date_to, _ = _period_range(period)
    extra: list = []
    if date_from:
        extra.append(["posting_date", ">=", date_from])
    if date_to:
        extra.append(["posting_date", "<=", date_to])

    rows = await engine.recent_entries(
        limit=constants.get("export_entries_limit"), extra_filters=extra, docstatus=(1,)
    )
    accs_all = await asyncio.gather(*(engine.entry_accounts(r["name"]) for r in rows))
    accounts = await engine.list_accounts()
    root_of = {a["name"]: a["root_type"] for a in accounts}

    reg_cur = money.registered_full()

    def _cur(accs):
        for a in (accs or []):
            if a in reg_cur:
                return reg_cur[a]["currency"]
        return money.DEFAULT_CURRENCY

    buckets: dict[tuple[str, str], dict] = {}

    def _bucket(date_str: str) -> str:
        d = datetime.fromisoformat(date_str).date()
        if group_by == "week":
            monday = d - timedelta(days=d.weekday())
            return monday.isoformat()
        if group_by == "month":
            return d.replace(day=1).isoformat()
        return d.isoformat()

    def _ensure(bucket: str, currency: str):
        key = (bucket, currency)
        return buckets.setdefault(key, {"date": bucket, "currency": currency,
                                        "income": 0.0, "expense": 0.0, "net": 0.0})

    for r, accs in zip(rows, accs_all):
        if not accs:
            continue
        debit, credit = accs[0], (accs[1] if len(accs) > 1 else None)
        amt = abs(float(r["total_debit"]))
        if not amt:
            continue
        b = _bucket(r["posting_date"])
        cur = _cur(accs)
        if root_of.get(debit) == "Expense":
            _ensure(b, cur)["expense"] += amt
        elif credit and root_of.get(credit) == "Income":
            _ensure(b, cur)["income"] += amt

    for b in buckets.values():
        b["net"] = round(b["income"] - b["expense"])
        b["income"] = round(b["income"])
        b["expense"] = round(b["expense"])

    out = sorted(buckets.values(), key=lambda x: (x["currency"], x["date"]))
    series = []
    currencies = sorted({p["currency"] for p in out})
    for cur in currencies:
        series.append({
            "currency": cur,
            "points": [
                {"label": p["date"][5:], "income": p["income"],
                 "expense": p["expense"], "net": p["net"]}
                for p in out if p["currency"] == cur
            ],
        })
    return {"period": period, "group_by": group_by, "series": series}


@router.get("/compare")
async def analytics_compare(period: str = "month", lang: str = "ru",
                            user_id: int = Depends(require_user)):
    """Current period totals vs previous matching period."""
    prev_map = {
        "last7": "prev_week",
        "week": "prev_week",
        "prev_week": "last7",
        "month": "prev_month",
        "prev_month": "month",
        "last30": "last90",
        "last90": "last30",
        "year": "prev_month",
        "all": "year",
    }
    prev_period = prev_map.get(period, "prev_month")

    def _totals(grp):
        return {
            "income": round(sum(g.get("income", 0) for g in grp)),
            "expense": round(sum(g.get("expense", 0) for g in grp)),
            "net": round(sum(g.get("net", 0) for g in grp)),
        }

    cur_from, cur_to, cur_label, cur_groups = await _report_groups(period, lang)
    prev_from, prev_to, prev_label, prev_groups = await _report_groups(prev_period, lang)

    cur_tot = _totals(cur_groups)
    prev_tot = _totals(prev_groups)

    def _pct(cur_v, prev_v):
        if not prev_v:
            return 0
        return round((cur_v - prev_v) / abs(prev_v) * 100)

    comparisons = []
    currencies = sorted({c for g in cur_groups + prev_groups for c in [g.get("currency")] if c})
    for cur in currencies:
        cg = next((g for g in cur_groups if g.get("currency") == cur), None) or {}
        pg = next((g for g in prev_groups if g.get("currency") == cur), None) or {}
        comparisons.append({
            "currency": cur,
            "current_label": cur_label,
            "previous_label": prev_label,
            "current": {
                "income": round(cg.get("income", 0)),
                "expense": round(cg.get("expense", 0)),
                "net": round(cg.get("net", 0)),
            },
            "previous": {
                "income": round(pg.get("income", 0)),
                "expense": round(pg.get("expense", 0)),
                "net": round(pg.get("net", 0)),
            },
            "growth": {
                "income_pct": _pct(cg.get("income", 0), pg.get("income", 0)),
                "expense_pct": _pct(cg.get("expense", 0), pg.get("expense", 0)),
                "net_pct": _pct(cg.get("net", 0), pg.get("net", 0)),
            },
        })

    return {
        "current": {"period": period, "date_from": cur_from, "date_to": cur_to, **cur_tot},
        "previous": {"period": prev_period, "date_from": prev_from, "date_to": prev_to, **prev_tot},
        "comparisons": comparisons,
    }
