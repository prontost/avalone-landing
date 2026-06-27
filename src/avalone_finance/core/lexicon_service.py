"""Business logic for the per-user learned lexicon.

The service normalizes raw user phrases before storing them and before lookup.
"""

from __future__ import annotations

from avalone_core.database import Service
from avalone_finance.core.lexicon_repository import LexiconRepository

_PREPOSITIONS = {"с", "со", "на", "из", "в", "за", "по", "от", "к"}


def _stem(word: str) -> str:
    # грубый стем: «карты/картой/картах» -> «карт». Для личного лексикона
    # (десятки слов, один пользователь) ложные склейки практически исключены.
    return word[:4] if len(word) > 4 else word


def _norm(phrase: str) -> str:
    words = [_stem(w) for w in phrase.lower().split() if w not in _PREPOSITIONS]
    return " ".join(words)


class LexiconService(Service):
    """Learned phrase -> account mapping for a single user."""

    def __init__(self, repository: LexiconRepository | None = None) -> None:
        self._repo = repository or LexiconRepository()

    def lookup(self, chat_id: int, kind: str, phrase: str) -> str | None:
        """Find an account matching the raw user phrase."""
        normalized = _norm(phrase or "")
        if not normalized:
            return None
        return self._repo.lookup(chat_id, kind, normalized)

    def save(self, chat_id: int, kind: str, phrase: str, account: str) -> None:
        """Store a raw user phrase -> account mapping."""
        if not phrase:
            return
        self._repo.save(chat_id, kind, _norm(phrase), account)
