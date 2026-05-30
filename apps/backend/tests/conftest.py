"""Fixtures globales de Pytest para el backend.

Las fixtures de DB (``db_engine`` / ``db_session``) corren contra
``TEST_DATABASE_URL`` — una DB de tests DEDICADA, NUNCA produccion ni la
Supabase real (las tablas de memoria son sagradas, regla #3). Si la env var
no esta seteada, los tests que las piden se SKIPean: el run default (sin el
marker ``integration``) no toca ninguna DB.

Para correr los tests de integracion localmente, levantar un Postgres con
pgvector y exportar la URL antes de pytest::

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/ynara_test \\
        python -m pytest -m integration

El Postgres de tests necesita pgvector >= 0.5.0 (indices HNSW de la migracion).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Forzar backend asyncio en pytest-anyio si llega a usarse."""
    return "asyncio"


def _test_database_url() -> str:
    """URL async (asyncpg) de la DB de tests. Vacio si TEST_DATABASE_URL no esta."""
    raw = os.environ.get("TEST_DATABASE_URL", "")
    if not raw:
        return ""
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


@pytest.fixture(scope="session")
def db_url() -> str:
    """URL de la DB de tests; SKIP si no hay TEST_DATABASE_URL (jamas prod)."""
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL no seteada (DB de tests dedicada, NO prod/Supabase)")
    return url


@pytest_asyncio.fixture
async def db_engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    """Engine async contra la DB de tests (function-scoped).

    Function scope + NullPool: cada test crea el engine en su PROPIO event loop
    y abre una conexion fresca por checkout. Evita el footgun de un engine
    session-scoped atado a un loop distinto al del test (pytest-asyncio crea un
    loop por test por defecto); recrear el engine con NullPool es trivial.
    """
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """AsyncSession por test; rollback al final para no persistir entre tests."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
