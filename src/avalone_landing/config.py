"""Runtime configuration for avalone.online portal.

Ветки/приложения теперь живут в едином реестре avalone_core.registry.
Этот файл отвечает только за deployment-настройки (host, port, secrets).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVALONE_", env_file=".env", extra="ignore")

    web_base_url: str = "https://avalone.online"
    web_host: str = "127.0.0.1"
    web_port: int = 8811
    fernet_key: str = "change-me-in-production"

    # Mail: either SMTP relay or local sendmail fallback.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    mail_from: str = "noreply@avalone.online"
    mail_from_name: str = "Avalone"

    # Comma-separated list of admin addresses to notify about new feedback.
    admin_email: str = ""



@lru_cache
def settings() -> Settings:
    return Settings()


# Единый реестр для импорта из портала.
from avalone_core.registry import AvaloneRegistry  # noqa: E402

__all__ = ["settings", "AvaloneRegistry"]
