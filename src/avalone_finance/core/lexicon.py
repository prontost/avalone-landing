"""Per-user learned lexicon: the user's words -> their accounts.

Третий слой архитектуры (Дэн, 2026-06-12): знания о словаре пользователя — это
ДАННЫЕ, не код и не промпт. «Карта» у одного — дебетовая, у другого — кредитка;
бот не угадывает: незнакомое слово -> один вопрос с вариантами -> ответ
сохраняется здесь навсегда. Каждое исправление тоже учит лексикон.
План счетов принадлежит пользователю: незнакомая категория -> выбор из похожих
/ создать новый счёт — никогда не форсить в «ближайший» молча.

Backward-compatible facade: module-level `lookup` and `save` delegate to the
default LexiconService instance.
"""

from avalone_finance.core.lexicon_repository import LexiconRepository
from avalone_finance.core.lexicon_service import LexiconService

# --- backward-compatible module-level API ---
_default_service = LexiconService()

lookup = _default_service.lookup
save = _default_service.save

__all__ = [
    "LexiconRepository",
    "LexiconService",
    "lookup",
    "save",
]
