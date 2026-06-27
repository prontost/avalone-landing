"""Shared helpers used by multiple API routers."""

from avalone_finance.core import catalog, money


# лексикон-неймспейс = текущий тенант (изоляция между пользователями)
def _lex_chat() -> int:
    from avalone_finance.core import tenant
    return tenant.current()


def _label(account: str) -> str:
    return account.rsplit(" - ", 1)[0]


def _clabel(a: dict, lang: str = "ru") -> str:
    """Localized label for an account dict (has 'name' and 'account_name' keys)."""
    return catalog.label(a["name"], a["account_name"], lang)


def _money_label(pk: str, raw: str, lang: str = "ru") -> str:
    """Имя денежного счёта. Приоритет: пользовательское имя из реестра money
    (переименование) -> catalog -> сырое имя ERPNext. Ключ pk СТАБИЛЕН — переезд
    имени не меняет id, на который ссылаются проводки/балансы."""
    return money.account_label(pk) or catalog.label(pk, raw, lang)


def _human_label(pk: str, account: dict | None, lang: str = "ru") -> str:
    """Человеческое имя счёта для UI: пользовательский ярлык (переименование)
    -> локализованный canon -> без суффикса ERPNext -> исходный pk."""
    custom = money.account_label(pk)
    if custom:
        return custom
    if account:
        return _clabel(account, lang)
    return _label(pk)


# Видимость категории в дроплистах: показываем, если счёт в каноне (по
# account_name) ИЛИ заведён пользователем (есть перевод в catalog_i18n).
# Так пользовательская «Бизнес» видна, а системный ERP-шум (Freight и пр.) — нет.
def _is_visible(a: dict) -> bool:
    return a["account_name"] in catalog.CANON or catalog.is_user_category(a["name"])
