"""Shared test fixtures and helpers for Counta.

Since production auth uses Avalone SSO, tests monkeypatch external_auth.user_id_of
to return the locally-set tenant id. This lets tests keep using the existing
 tenant.* helpers while exercising the same middleware path as production.
"""

import pytest


@pytest.fixture(autouse=True)
def _patch_external_auth_for_tests(monkeypatch):
    """Make auth_gate trust the in-process tenant context."""
    import avalone_finance.core.external_auth as external_auth
    import avalone_finance.core.tenant as tenant

    def _fake_user_id_of(request):
        return tenant.current()

    monkeypatch.setattr(external_auth, "user_id_of", _fake_user_id_of)
