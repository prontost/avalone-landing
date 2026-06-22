# avalone.online landing

Простой лендинг/каталог для приложений под зонтом `avalone.online`.

- Counta: https://counta.avalone.online

## Запуск локально

```bash
uv sync
uv run python -m uvicorn avalone_landing.web.app:app --host 127.0.0.1 --port 8811
```

## Проверка

```bash
uv run python scripts/pre_flight.py
```

## Добавить новое приложение

Отредактируй `src/avalone_landing/config.py` — добавь элемент в список `APPS`.
