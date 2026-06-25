"""Runtime configuration and universe branches for avalone.online portal."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVALONE_", env_file=".env", extra="ignore")

    web_base_url: str = "https://avalone.online"
    web_host: str = "127.0.0.1"
    web_port: int = 8811
    fernet_key: str = "change-me-in-production"


@lru_cache
def settings() -> Settings:
    return Settings()


# Branches of the Avalone metaverse.
# Each branch represents a life area. Active branches link to real apps,
# coming-soon branches show a teaser and (optionally) a waitlist form.
BRANCHES = [
    {
        "id": "work",
        "name": "Работа",
        "name_en": "Work",
        "name_ko": "일",
        "icon": "🛠️",
        "description": "Арбайт, смены, поездки, фриланс, карьера.",
        "status": "in_dev",
        "app_id": "work",
        "url": "https://routa.avalone.online",
        "actions": [
            {"label": "Work", "url": "https://routa.avalone.online"},
        ],
    },
    {
        "id": "money",
        "name": "Финансы",
        "name_en": "Finance",
        "name_ko": "재정",
        "icon": "🪙",
        "description": "Учёт, бюджет, аналитика, советы.",
        "status": "active",
        "app_id": "counta",
        "url": "https://counta.avalone.online",
        "actions": [
            {"label": "Counta", "url": "https://counta.avalone.online"},
        ],
    },
    {
        "id": "education",
        "name": "Образование",
        "name_en": "Education",
        "name_ko": "교육",
        "icon": "📚",
        "description": "Курсы, языки, переподготовка, адаптация.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
    {
        "id": "housing",
        "name": "Жильё",
        "name_en": "Housing",
        "name_ko": "주거",
        "icon": "🏠",
        "description": "Аренда, соседи, бытовые вопросы.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
    {
        "id": "tourism",
        "name": "Туризм",
        "name_en": "Tourism",
        "name_ko": "관광",
        "icon": "✈️",
        "description": "Трансферы, экскурсии, путешествия.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
    {
        "id": "health",
        "name": "Здоровье",
        "name_en": "Health",
        "name_ko": "건강",
        "icon": "🏥",
        "description": "Клиники, страховка, записи.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
    {
        "id": "transport",
        "name": "Транспорт",
        "name_en": "Transport",
        "name_ko": "교통",
        "icon": "🚐",
        "description": "Маршруты, водители, передвижение.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
    {
        "id": "community",
        "name": "Сообщества",
        "name_en": "Community",
        "name_ko": "커뮤니티",
        "icon": "🌐",
        "description": "Люди, группы, мероприятия, помощь.",
        "status": "coming_soon",
        "url": None,
        "actions": [],
    },
]

# Legacy catalog kept for API compatibility.
APPS = [
    {
        "id": "counta",
        "name": "Counta",
        "icon": "🪙",
        "description": "Деньги перестают течь сквозь пальцы: учёт, аналитика, советы.",
        "url": "https://counta.avalone.online",
    },
    {
        "id": "work",
        "name": "Work",
        "icon": "🛠️",
        "description": "Рабочая координация: поездки, смены, задачи, команда.",
        "url": "https://routa.avalone.online",
    },
]
