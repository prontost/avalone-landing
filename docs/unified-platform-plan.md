# План варианта A: единая SQLite-база + единый источник истины

## Цель

Превратить три отдельных приложения с тремя SQLite-базами в одну платформу Avalone с единой базой данных, единой моделью пользователя и единым источником истины для приложений, веток, навигации и текстов.

## Текущее состояние (проблемы)

- `~/.avalone/avalone.db` — только `users`.
- `~/.counta/counta.db` — `users`, `external_users`, `money_*`, `led_*`, `catalog_i18n`, `notifications` и т.д. (legacy-файл данных модуля Финансов).
- `~/.routa/routa.db` — `users`, `external_users`, `money_*`, `led_*`, `catalog_i18n`, `notifications`, `trips`, `trip_members` (legacy-файл данных модуля Работы).
- В Avalone пользователь `lucifer` имеет `id=1`.
- В Финансы/Работа `external_users` хранит: `avalone|1|3` — лишняя косвенность.
- Fallback-логин в Финансы/Работа создаёт тенанты и пароли, дублируя пользователей Avalone.
- На landing есть раздел «Профиль» в быстрых действиях, который помечен как "в разработке", но страница `/profile` уже работает — противоречие.
- Названия веток, URL, иконки и статусы дублируются в `config.py`, шаблонах и JS.

## Желаемое состояние

- Одна БД: `~/.avalone/avalone.db` (или `~/.avalone/platform.db`).
- Единая таблица `users`.
- Нет `external_users` и fallback-логина.
- Tenant_id = user_id из `users`.
- Таблицы модулей с префиксами:
  - `money_accounts`, `money_led_entries`, `money_catalog_i18n`, `money_notifications`…
  - `work_trips`, `work_trip_members`, `work_catalog_i18n`, `work_notifications`…
- Единый реестр приложений/веток (`AvaloneRegistry`), который используется порталом, Финансы, Работа, shell, PWA manifest.
- Landing не содержит противоречий и не обманывает пользователя статусами.

## Архитектура

```
avalone_online/
├── src/
│   ├── avalone_landing/          # портал + SSO
│   ├── avalone_money/            # модуль Финансов
│   ├── avalone_work/             # модуль Работы
│   └── avalone_core/             # общее ядро
│       ├── db.py                 # единое подключение, миграции
│       ├── registry.py           # AvaloneRegistry
│       ├── tenant.py             # TenantContext
│       ├── auth.py               # SSO cookie, no fallback
│       └── glossary.py           # единый глоссарий
```

## Компоненты ядра

### 1. `AvaloneRegistry` (единый реестр)

```python
@dataclass
class AppBranch:
    id: str
    name_key: str          # ключ в глоссарии
    icon: str
    description_key: str   # ключ в глоссарии
    status: Literal["active", "in_dev", "planned"]
    url: str | None
    module: Literal["portal", "money", "work", None]

class AvaloneRegistry:
    BRANCHES: list[AppBranch]

    @classmethod
    def active(cls) -> list[AppBranch]: ...
    @classmethod
    def by_id(cls, branch_id: str) -> AppBranch | None: ...
    @classmethod
    def app_nav(cls, current_module: str) -> list[dict]: ...
```

Используется в:
- `avalone_landing/config.py`
- `avalone_landing/web/templates/landing.html`
- `avalone_landing/web/templates/profile.html`
- `src/avalone_finance/web/templates/app.html`
- `src/avalone_work/web/templates/work.html` (когда модуль Работы появится)
- `avalone_landing/web/templates/shell.html`

### 2. `TenantContext`

```python
class TenantContext:
    _current: contextvars.ContextVar[int]

    @classmethod
    def set(cls, user_id: int): ...
    @classmethod
    def get(cls) -> int: ...
```

### 3. `UnifiedDB`

```python
class UnifiedDB:
    PATH: Path

    @classmethod
    def connection(cls) -> sqlite3.Connection: ...
    @classmethod
    def migrate(cls): ...
```

## Этапы работы

### Этап 1. Подготовка

1. Сделать полные бэкапы:
   - `~/.avalone/avalone.db`
   - `~/.counta/counta.db`
   - `~/.routa/routa.db`
2. Зафиксировать текущие версии всех репозиториев (`git status`).
3. Создать отдельную ветку `feature/unified-db` в каждом репозитории (или одну общую, если репозитории объединены).

### Этап 2. Единый реестр приложений

1. Создать `src/avalone_core/registry.py` с `AvaloneRegistry`.
2. Перенести туда все ветки из `config.py` Avalone landing.
3. Удалить дублирующие `BRANCHES` из Финансы/Работа шаблонов — передавать из `AvaloneRegistry`.
4. Обновить `shell.html` для рендеринга статусов из реестра.
5. **Критерий:** в поиске по проекту `grep -R "Работа\|Финансы\|Обучение\|Жильё\|Поездки\|Здоровье"` встречается только в `registry.py` и глоссарии, но не захардкожено в шаблонах.

### Этап 3. Единая база данных

1. Создать `src/avalone_core/db.py`:
   - `USERS_TABLE`
   - `MONEY_TABLES` (prefixed)
   - `WORK_TABLES` (prefixed)
   - `migrate()` — idempotent DDL.
2. Скопировать структуру таблиц из Финансы/Работа с префиксами.
3. Мигрировать данные:
   - Avalone `users` → `users`.
   - Финансы tenant 3 (`lucifer`) → `money_*` с `tenant_id=1`.
   - Работа tenant 3 (`lucifer`) → `work_*` с `tenant_id=1`.
   - Финансы/Работа `external_users` удалить.
4. Удалить fallback-логин и таблицы `users` в Финансы/Работа.
5. **Критерий:** `sqlite3 ~/.avalone/avalone.db ".tables"` показывает `users`, `money_*`, `work_*` и не показывает `external_users` в модулях.

### Этап 4. Обновление приложений

1. Avalone landing:
   - Использовать `AvaloneRegistry`.
   - Подключаться к unified DB для users.
2. Модуль Финансы:
   - Подключаться к unified DB с префиксом `money_`.
   - Убрать `/login`, `/register`, `/recover`, `/reset` fallback.
   - Убрать legacy-cookie модуля Финансов, оставить только Avalone SSO.
   - Удалить шаблоны `login.html`, `register.html` Финансы.
3. Работа (Работа):
   - Подключаться к unified DB с префиксом `work_`.
   - Убрать fallback-логин.
   - Удалить `login.html` Работа.
4. **Критерий:** авторизация только через Avalone; Финансы/Работа не имеют собственных страниц логина.

### Этап 5. Исправление landing

1. В «Быстрых действиях» убрать провокационные статусы.
2. Профиль — активная ссылка на `https://avalone.online/profile`.
3. Чат/сообщества — помечены «В планах» и ведут на teaser.
4. Все статусы берутся из `AvaloneRegistry`.
5. **Критерий:** нет фраз «в разработке» / «скоро» рядом с уже работающими функциями.

### Этап 6. Рефакторинг кода

1. Вынести общие утилиты в `avalone_core`.
2. Использовать dataclasses / Pydantic модели для сущностей.
3. Разделить слои:
   - `core/` — бизнес-логика и БД.
   - `web/` — HTTP/шаблоны.
   - `api/` — API endpoints.
4. Убрать дублирование между Финансы и Работа (общий ledger, общие настройки).
5. **Критерий:** `grep -R "TODO\|FIXME\|HACK"` в `src/` не показывает критичных мест.

### Этап 7. Тестирование

1. Написать/обновить тесты:
   - Регистрация/логин Avalone.
   - SSO в Финансы и Работа.
   - CRUD операций в Финансы.
   - CRUD поездок в Работа.
2. Проверить мобильную адаптацию 320/375/768/1440.
3. Проверить PWA manifest/sw для всех модулей.
4. **Критерий:** все тесты green, pre-flight green, i18n линтер чист.

### Этап 8. Переключение production

1. Остановить сервисы.
2. Перенести unified DB в production location.
3. Обновить launchd plist: убрать `COUNTA_DB_PATH`, `ROUTA_DB_PATH`, оставить одну `AVALONE_DB_PATH`.
4. Перезапустить сервисы.
5. Проверить end-to-end: вход lucifer → Финансы/Работа → данные на месте.

## Критерии приёмки

### Обязательные

- [ ] Единая БД `~/.avalone/avalone.db` содержит `users`, `money_*`, `work_*` таблицы.
- [ ] Нет fallback-логина в Финансы/Работа; вход только через Avalone SSO.
- [ ] Нет аккаунта `owner` в production DB.
- [ ] `AvaloneRegistry` — единственное место с определением веток/приложений.
- [ ] Глоссарий — единственное место с пользовательскими текстами.
- [ ] Landing не содержит противоречий в статусах.
- [ ] Все тесты проходят; pre-flight green; i18n чист.
- [ ] Авторизация lucifer → Финансы/Работа → данные lucifer, не owner.

### UX/UI

- [ ] Единая шапка Avalone на всех страницах.
- [ ] Переходы между порталом, Финансами, Работой сохраняют сессию.
- [ ] Мобильная версия 320–1440 px без горизонтального скролла.
- [ ] Все страницы имеют понятные заголовки и статусы.

### Код

- [ ] Нет дублирования `BRANCHES` / `APPS` в разных файлах.
- [ ] Нет хардкода URL/статусов в шаблонах.
- [ ] Модули используют `avalone_core` для общих вещей.
- [ ] Каждый модуль имеет понятную структуру `core/` / `web/` / `api/`.

## Вариант B (PostgreSQL)

- Перенос unified schema на PostgreSQL.
- Alembic для миграций.
- Поднять после того, как вариант A отработан и принят.
- Напоминание: раз в неделю спрашивать пользователя, готов ли перейти к варианту B.

## Риски

- Миграция данных из трёх БД в одну — критичная операция. Всегда делать бэкап.
- Удаление fallback-логина: если Avalone SSO сломается, админ не зайдёт без восстановления. Нужно иметь CLI-команду экстренного доступа.
- Рефакторинг большого `app.html` Финансы может сломать JS. Нужны тесты и постепенные изменения.
