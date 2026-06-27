"""Tunable instance constants.

Every hardcoded numeric/string threshold that affects runtime behaviour lives
here with a default. Admins can override any value via global_settings; the
override is read from DB on each call, so changes apply without restart.

Values are stored as TEXT in global_settings and coerced back to the type of
the default. If coercion fails, the default is used.
"""

from decimal import Decimal
from typing import Any

from avalone_finance.core import global_settings

DEFAULTS: dict[str, Any] = {
    # --- security / auth ---
    "rate_limit_window_sec": 300,
    "max_login_attempts": 8,
    "max_register_attempts": 5,
    "max_verify_attempts": 10,
    "max_recover_attempts": 5,
    "min_login_length": 3,
    "min_password_length": 6,
    "session_max_age_days": 90,
    "accounts_max_age_days": 90,
    "password_reset_token_entropy": 32,  # secrets.token_urlsafe(n)

    # --- ledger / UX ---
    "recent_entries_limit": 200,
    "export_entries_limit": 10_000,
    "find_entry_limit": 30,

    # --- logging ---
    "log_max_bytes": 5 * 1024 * 1024,
    "log_backup_count": 3,

    # --- misc ---
    "qr_default_size": 200,
    "build_id_hash_length": 12,
}


def _coerce(name: str, raw: str) -> Any:
    default = DEFAULTS[name]
    try:
        if isinstance(default, bool):
            return raw.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, Decimal):
            return Decimal(raw)
        return raw
    except Exception:
        return default


def get(name: str) -> Any:
    """Return current effective value for a tunable constant."""
    if name not in DEFAULTS:
        raise KeyError(f"unknown constant: {name}")
    override = global_settings.get(name)
    if override is None:
        return DEFAULTS[name]
    return _coerce(name, override)


def all_effective() -> dict[str, Any]:
    """All constants with their current effective values."""
    return {name: get(name) for name in DEFAULTS}
