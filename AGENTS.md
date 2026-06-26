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
- **Git-репозитории платформы:** `~/github-work/counta`, `~/github-work/routa`, `~/github-work/avalone.online`

После любого изменения кода/конфига/базы запускать бэкап и пушить все грязные репозитории из списка.

## Безопасность

- Секреты проекта хранить в `~/infrastructure-secrets.env` или project-specific `.env` (в `.gitignore`).
- Не коммитить API-ключи, пароли, токены.
- Репозиторий публичный — не публиковать персональные данные оператора или третьих лиц.
