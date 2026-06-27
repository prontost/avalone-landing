# AGENTS.md — проект avalone.online

> Project-specific instructions для метавселенной Avalone.
> Глобальные предпочтения оператора: `~/AGENTS.md`
> Канонический контекст: `~/github-work/denis-root-continuity/skills/`

## Project header

- **Selected template:** `software-project-rules` + `project-rules`
- **Named source basis:** RUP, ISO/IEC/IEEE 12207, 29148, 14764, IEEE 828, Google eng-practices, ToIP stack
- **Tailoring notes:** проект находится в фазе зарождения идеи + прототипирования. Исследования и документирование продолжаются параллельно с созданием работающего портала и первой ветки.
- **Current phase:** Inception / concept + Domain research + Portal prototype + Identity design
- **Current gate status:** концепция сформулирована, сущности выделены, архитектура уровней, проработан первый сценарий, работает портал с ветками, спроектирована единая авторизация
- **Next exact slice:** добавить phone auth в Avalone portal

## Read order для проекта

1. `README.md` — обзор проекта и структура документации.
2. `docs/avalone-meta.md` — текущее состояние метавселенной.
3. `docs/research.md` — результаты исследований.
4. `~/github-work/denis-root-continuity/skills/project-avalone.md` — контекст домена avalone.online.
5. `~/github-work/denis-root-continuity/skills/software-project-rules.md` — методология.
6. `~/github-work/denis-root-continuity/skills/project-rules.md` — кросс-доменные правила.

## Принципы проекта

1. **Не сужать до MVP без одобрения.** Оператор явно сказал, что сейчас режим планирования и проработки идеи, а не выбора MVP.
2. **Не терять видение метавселенной.** Любое техническое решение должно расширять ядро, а не создавать отдельный остров.
3. **Любая новая идея — через призму сущностей:** Человек → Организация → Место → Событие → Возможность → Навык → Документ → Транспорт → Сообщество → Репутация.
4. **Source citation обязательна** для process guidance, методологий, паттернов.
5. **Документировать перед кодом.** Пока нет durable project state в виде документов, код не пишется.

## Чувствительные темы

- Проект связан с доходом оператора и его мечтой о независимости от локации.
- Не обесценивать масштаб идеи, но и не обещать лёгкого успеха.
- Бюджет и личные финансы оператора — отдельно, см. `~/github-work/denis-root-continuity/skills/family-budget/SKILL.md`.

## Backup, commit и push

> Конкретика для правила «после любого изменения — бэкап + коммит + пуш».
> Само правило живёт в скилле `git-commit-push`, здесь только пути и параметры.

- **Бэкап баз:** `infra/backup/backup_db.py`
- **Конфиг бэкапа:** `infra/backup/backup-config.json` (список путей к `.db`)
- **Глубина архива:** 14 дней, автоматическая ротация
- **Расписание:** launchd-агент `online.avalone.db-backup`, каждый час
- **Бэкапы складываются в:** `~/.avalone/backups/auto/`
- **Git-репозиторий платформы:** `~/github-work/avalone.online`
- **Удалённые репозитории Counta/Routa:** ещё не удалены на GitHub вручную (требуется scope `delete_repo`)

После любого изменения кода/конфига/базы запускать бэкап и пушить изменения в `~/github-work/avalone.online`.

## Безопасность

- Секреты проекта хранить в `~/infrastructure-secrets.env` или project-specific `.env` (в `.gitignore`).
- Не коммитить API-ключи, пароли, токены.
- Репозиторий публичный — не публиковать персональные данные оператора или третьих лиц.

## Class-based architecture (enforced)

All new and refactored code must be organized as classes. Free functions with business logic are no longer allowed in `core/` or `web/api/`.

### Layer rules

| Layer | Naming | Responsibility |
|-------|--------|----------------|
| Domain models | `User`, `Account`, `Entry`, `Trip`, ... | `dataclasses`/`pydantic.BaseModel` with data and validation only. |
| Repositories | `*Repository` | SQL only. One repository per aggregate root. Receive `Database`/`Connection` via constructor. |
| Services | `*Service` | Business logic, rules, orchestration. Depend on repositories and other services via constructor. |
| API routers | `*router` (FastAPI) | Thin: validate input, call service via `Depends(get_*_service)`, return response. |
| Infrastructure | `Database`, `UnitOfWork`, `Settings` | Connection management, config, logging. |

### Hard rules

- One public class per file, named after the file (`PascalCase`).
- No top-level business functions in `core/*.py` or `web/api/*.py`. Private helpers inside classes are OK.
- All SQL lives in repositories.
- All `glossary.t(...)` calls live in services or repositories, never in templates (templates already use `t()` via Jinja).
- API endpoints use FastAPI `Depends` to get services; services are instantiated once per request (or shared via `request.state`).
- Prefer constructor injection. Avoid module-level mutable state.

### Example: adding a new endpoint

1. Add/update domain model in `core/models.py` (or domain-specific file).
2. Add repository method in `core/<aggregate>_repository.py`.
3. Add service method in `core/<domain>_service.py`.
4. Expose via `get_<domain>_service()` in `web/api/dependencies.py`.
5. Add endpoint in `web/api/<domain>.py` using `Depends(...)`.

### Example: adding a new entity

```python
# core/models.py
from dataclasses import dataclass

@dataclass
class Trip:
    id: int
    direction: str
    date: str

# core/trip_repository.py
class TripRepository:
    def __init__(self, db):
        self._db = db

    def list_for_tenant(self, tenant_id: int) -> list[Trip]: ...

# core/trip_service.py
class TripService:
    def __init__(self, repo: TripRepository):
        self._repo = repo

    def upcoming(self, tenant_id: int) -> list[Trip]: ...

# web/api/dependencies.py
def get_trip_service() -> TripService: ...

# web/api/trips.py
from fastapi import APIRouter, Depends
from avalone_landing.core.trip_service import TripService
from avalone_landing.web.api.dependencies import get_trip_service

router = APIRouter()

@router.get("/trips")
async def list_trips(service: TripService = Depends(get_trip_service)):
    return service.upcoming(...)
```

## Internationalization (i18n) and glossary

All user-facing text must live in the glossary. No hardcoded strings in templates or code.

- Use `t('key', lang=lang)` in Jinja2 templates.
- Use `glossary.t('key', lang=...)` in Python services/repositories.
- Every new key must be added to:
  1. `src/avalone_core/avalone_core/glossary_db.py` seed data (at least `ru`, `en`, `ko`).
  2. `src/avalone_core/avalone_core/ui_glossary.py` `EXACT` or `PREFIX` with a **precise, unambiguous description**.

### Writing translation-friendly source text

- State the **screen/location** where the string appears.
- State the **control type**: button label, heading, placeholder, tooltip, error message, alt text, etc.
- Mention any **placeholders** (`{name}`, `{count}`) and what they will contain.
- Avoid idioms, abbreviations, culture-specific jokes, and ambiguous pronouns.
- Keep sentences short and use plain language so cheap/machine translation produces correct results.
- If a string has a length constraint, note it.
- If a term is a brand name or should not be translated, say so explicitly.

Example of a good description:

```python
"shell_invite_share_btn": (
    "Button label inside the invite-friend modal that opens the native OS share sheet. "
    "The user has already opened the modal from the burger menu. "
    "Use the verb that means 'share via the phone/computer system dialog', not 'split' or 'divide'."
),
```

### Quality bar

- Korean and any other non-English translation must be reviewed by a native speaker before being shown to end users.
- Until review, prefer a clearly correct but plain translation over a clever one.
- Do not leave empty translations; fall back to English if a proper translation is not ready.
