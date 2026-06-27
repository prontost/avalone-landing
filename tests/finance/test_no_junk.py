"""Страж чистоты боевой БД: в counta.db не должно быть записей с тест-маркерами.

Если этот тест падает — кто-то (включая меня, ИИ) прогнал тест на боевой
counta.db вместо temp-БД и оставил мусор. Все тестовые прогоны ОБЯЗАНЫ идти в
изолированной БД (monkeypatch core.db.DB_PATH), не в ~/.counta/counta.db.
"""
from pathlib import Path

import pytest

# маркеры, которыми помечается тестовый/dev-мусор
JUNK_MARKERS = (
    "contract-test", "pwa e2e", "кпз", "ledger-live", "cancel-edit",
    "zz-", "пробн", "проверка test", "тест-страж",
)


@pytest.mark.skipif(
    not (Path.home() / ".counta" / "counta.db").exists(),
    reason="боевой counta.db отсутствует (CI/чистая среда) — нечего проверять",
)
def test_prod_ledger_has_no_junk():
    import sqlite3
    db = Path.home() / ".counta" / "counta.db"
    con = sqlite3.connect(db)
    try:
        # таблица леджера может отсутствовать на свежей БД — тогда мусора нет
        has = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='led_entries'"
        ).fetchone()
        if not has:
            return
        rows = con.execute("SELECT name, user_remark FROM led_entries").fetchall()
    finally:
        con.close()
    junk = [r[0] for r in rows
            if any(m in (r[1] or "").lower() for m in JUNK_MARKERS)]
    assert not junk, (
        f"в боевом counta.db {len(junk)} тест-записей: {junk[:10]} — "
        f"прогоняй тесты на temp-БД, не на боевой!")
