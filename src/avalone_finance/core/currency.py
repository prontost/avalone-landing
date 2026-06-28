"""Валюты и живой курс — backward-compatible facade over CurrencyService.

Источники курса (бесплатные, без ключа):
- фиат: open.er-api.com (USD-базис, без ключа, обновляется ежедневно);
- крипта: api.coingecko.com (simple/price, без ключа).
Если источник недоступен — конвертация возвращает None, форма не подставит
мусор (пользователь введёт сумму вручную).

Этот слой портативен: при уходе от ERPNext (Вариант 2, перенос леджера в
avalone.db) он остаётся как есть.

Реализация теперь живёт в ``avalone_finance.core.currency_service``. Этот
модуль сохраняет старый API на уровне функций/констант, пробрасывая вызовы в
дефолтный экземпляр ``CurrencyService``.
"""

from __future__ import annotations

from avalone_finance.core.currency_service import (
    ALL,
    CRYPTO,
    CurrencyService,
    FIAT,
)

# Backward-compatible module-level constants.
FIAT = FIAT
CRYPTO = CRYPTO
ALL = ALL

_default_service: CurrencyService | None = None


def _service() -> CurrencyService:
    global _default_service
    if _default_service is None:
        _default_service = CurrencyService()
    return _default_service


def is_crypto(code: str) -> bool:
    return _service().is_crypto(code)


def known(code: str | None) -> bool:
    return _service().known(code)


def seed_glossary() -> int:
    """Засеять названия валют в единый глоссарий (kind='currency', ключи
    cur_<code>). Сейчас в EN из таблиц FIAT/CRYPTO; ru/ko можно дополнить в
    глоссарии позже (источник истины — глоссарий). Вызывается на старте."""
    return _service().seed_glossary()


def name(code: str, lang: str = "en") -> str:
    """Локализованное название валюты из глоссария; фолбэк — EN из таблицы."""
    return _service().name(code, lang)


def options(lang: str = "en") -> dict[str, list[dict]]:
    """Списки для дроплиста: {fiat:[{code,name,symbol}...], crypto:[...]}.
    name — локализованное имя из глоссария (источник истины)."""
    return _service().options(lang)


async def _fiat_usd_rates() -> dict[str, float] | None:
    """USD-базисные курсы для фиата: {code: units_per_USD}. Без ключа, без кэша."""
    return await _service()._fiat_usd_rates()


async def _crypto_usd_price(codes: list[str]) -> dict[str, float] | None:
    """USD-цена за 1 монету для крипто-кодов: {code: usd_per_coin}."""
    return await _service()._crypto_usd_price(codes)


async def usd_value(code: str) -> float | None:
    """Сколько USD стоит 1 единица валюты `code` (фиат или крипта). None если нет данных."""
    return await _service().usd_value(code)


async def convert(amount: float, frm: str, to: str) -> float | None:
    """Перевести сумму из валюты frm в to по живому курсу. None если нет данных.
    Кросс-курс через USD (общий базис для фиата и крипты)."""
    return await _service().convert(amount, frm, to)
