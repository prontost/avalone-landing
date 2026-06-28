# avalone.online

> Цифровая метавселенная реального мира.
> Начало — с координации временных работников в Южной Корее.
> Перспектива — единый цифровой слой для работы, образования, туризма, медицины, жилья, транспорта и сообществ.

## Что это

`avalone.online` — это не лендинг и не отдельное приложение. Это домен-зонтик и проект по созданию социально-экономической метавселенной.

Ключевая идея: один профиль, один граф связей, одна репутация и множество веток жизни поверх них.

## Документация

- [`docs/avalone-meta.md`](docs/avalone-meta.md) — текущее состояние метавселенной: предыстория, эволюция идеи, фундаментальные сущности, архитектура уровней, ветки.
- [`docs/research.md`](docs/research.md) — результаты исследований по миру: super apps, HR/gig-платформы Кореи, графовые модели, identity/reputation standards.
- [`docs/research-insights.md`](docs/research-insights.md) — глубокий анализ и инсайты из исследований.
- [`docs/operator-context.md`](docs/operator-context.md) — сырой контекст оператора (твои наблюдения и слова).
- [`docs/commute-scenario.md`](docs/commute-scenario.md) — детальный сценарий поездок на работу.
- [`docs/portal-navigation.md`](docs/portal-navigation.md) — концепция навигации по порталу метавселенной.
- [`docs/tech-stack.md`](docs/tech-stack.md) — предварительный технологический стек.
- [`docs/identity-architecture.md`](docs/identity-architecture.md) — единая авторизация Avalone для всех веток.

## Текущее состояние

- **Фаза:** раннее планирование, исследования, проработка первого сценария + работающий портал.
- **Реализовано:**
  - Портал `avalone.online` с инфраструктурой метавселенной: активные и coming-soon ветки.
  - Активные ветки: **Работа** и **Финансы** — обе как модули единой платформы Avalone.
  - Документация проекта в `docs/`.
- **Следующий шаг:** наполнить ветку «Работа» реальным функционалом поездок на работу.

## Запуск

### Локально

```bash
uv sync
uv run python -m uvicorn avalone_landing.web.app:app --host 127.0.0.1 --port 8811
```

### Продакшен (macOS / launchd)

Сайт запускается как системный сервис через `launchd` и не зависит от сессии агента:

- Профиль: `~/Library/LaunchAgents/online.avalone.landing.plist`
- Логи: `~/Library/Logs/avalone-landing.log`
- Порт: `127.0.0.1:8811`

```bash
# Перезапуск
launchctl unload ~/Library/LaunchAgents/online.avalone.landing.plist
launchctl load ~/Library/LaunchAgents/online.avalone.landing.plist

# Статус
launchctl list | grep online.avalone.landing
```

## Проверка

```bash
uv run python scripts/pre_flight.py
```

## Добавить новую ветку в landing

Отредактируй `src/avalone_core/avalone_core/registry.py` — добавь элемент в `AvaloneRegistry._BRANCHES`.

## Канон оператора

Глобальные предпочтения оператора и правила работы с проектами:
- `~/AGENTS.md`
- `~/github-work/denis-root-continuity/skills/`
