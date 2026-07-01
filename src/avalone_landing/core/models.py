"""Domain models for the Avalone portal identity layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    login: str
    email: str
    created_at: str
    name: str = ""
    email_verified: bool = False
    is_admin: bool = False
    language: str = "auto"
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
