"""Runtime configuration and app catalog for avalone.online landing."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVALONE_", env_file=".env", extra="ignore")

    web_base_url: str = "https://avalone.online"
    web_host: str = "127.0.0.1"
    web_port: int = 8811


@lru_cache
def settings() -> Settings:
    return Settings()


# Catalog of apps hosted under the avalone.online umbrella.
# Each entry is shown as a card on the landing page.
APPS = [
    {
        "id": "counta",
        "name": "Counta",
        "icon": "🪙",
        "description": "Деньги перестают течь сквозь пальцы: учёт, аналитика, советы.",
        "url": "https://counta.avalone.online",
    },
    {
        "id": "routa",
        "name": "Routa",
        "icon": "🚐",
        "description": "Организация поездок людей на работу: маршруты, места, уведомления.",
        "url": "https://routa.avalone.online",
    },
]
