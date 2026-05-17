"""Fixtures globales de Pytest para el backend.

TODO: implementar:
- ``db_url`` desde env var ``TEST_DATABASE_URL`` (DB de tests, NO
  producción, NO Supabase real).
- ``engine`` y ``session`` async para cada test.
- ``client`` de httpx para integration tests del FastAPI.
- ``celery_eager`` para tests que tocan workers.

Por ahora deja el esqueleto.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Forzar backend asyncio en pytest-anyio si llega a usarse."""
    return "asyncio"


# TODO: db_engine, db_session, client, celery_eager fixtures.
