"""Единый реестр приложений/веток Avalone.

Единственный источник истины для:
- списка веток на портале;
- переключателя приложений в shell;
- PWA manifest / app navigation;
- статусов (active / in_dev / planned).
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AppBranch:
    id: str
    name_key: str       # ключ в глоссарии (app_money, ...)
    icon: str
    description_key: str
    status: Literal["active", "in_dev", "planned"]
    url: str | None
    module: Literal["portal", "money", None]


class AvaloneRegistry:
    _BRANCHES: tuple[AppBranch, ...] = (
        AppBranch(
            id="money",
            name_key="app_money",
            icon="🪙",
            description_key="app_money_desc",
            status="active",
            url="https://counta.avalone.online",
            module="money",
        ),
        AppBranch(
            id="education",
            name_key="app_education",
            icon="📚",
            description_key="app_education_desc",
            status="planned",
            url=None,
            module=None,
        ),
        AppBranch(
            id="living",
            name_key="app_living",
            icon="🏠",
            description_key="app_living_desc",
            status="planned",
            url=None,
            module=None,
        ),
        AppBranch(
            id="travel",
            name_key="app_travel",
            icon="✈️",
            description_key="app_travel_desc",
            status="planned",
            url=None,
            module=None,
        ),
        AppBranch(
            id="health",
            name_key="app_health",
            icon="🏥",
            description_key="app_health_desc",
            status="planned",
            url=None,
            module=None,
        ),
    )

    @classmethod
    def branches(cls) -> tuple[AppBranch, ...]:
        return cls._BRANCHES

    @classmethod
    def by_id(cls, branch_id: str) -> AppBranch | None:
        for b in cls._BRANCHES:
            if b.id == branch_id:
                return b
        return None

    @classmethod
    def active(cls) -> tuple[AppBranch, ...]:
        return tuple(b for b in cls._BRANCHES if b.status == "active")

    @classmethod
    def for_shell(cls, lang: str = "ru") -> list[dict]:
        """Формат, ожидаемый shell.html и landing.html."""
        from avalone_core.glossary import t
        return [
            {
                "id": b.id,
                "name": t(b.name_key, lang),
                "icon": b.icon,
                "description": t(b.description_key, lang),
                "status": b.status,
                "url": b.url,
            }
            for b in cls._BRANCHES
        ]

    @classmethod
    def app_nav(cls, current_module: str, lang: str = "ru") -> list[dict]:
        """Нижняя/боковая навигация внутри модуля."""
        from avalone_core.glossary import t
        if current_module == "money":
            return [
                {"label": t("nav_balances", lang), "icon": "💰", "href": "/#balances"},
                {"label": t("nav_journal", lang), "icon": "🧾", "href": "/#journal"},
                {"label": t("nav_analytics", lang), "icon": "📊", "href": "/#analytics"},
                {"label": t("nav_settings", lang), "icon": "⚙️", "href": "/#more"},
            ]
        return []
