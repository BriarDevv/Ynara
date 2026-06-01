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
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Forzar backend asyncio en pytest-anyio si llega a usarse."""
    return "asyncio"


@pytest.fixture(autouse=True)
def _default_token_store() -> None:
    """Monta un ``InMemoryTokenStore`` en ``app.state`` para todos los tests.

    Bajo ``ASGITransport`` el lifespan de ``app/main.py`` no corre, así que
    ``app.state.token_store`` (que ``get_current_user``/``get_current_claims``
    consumen desde issue #63) no existe. Igual que los tests ya inyectan a mano
    los Fakes de LLM/embedder, acá sembramos un store en memoria por default
    (nada blocklisteado, sin rate-limit efectivo) para que las rutas protegidas
    no exploten. Los tests de auth que necesitan un store específico lo
    overridean vía ``get_token_store`` sin tocar esto.
    """
    # Import local para no atar el conftest a app.state si la app no se importa.
    from app.core.token_store import InMemoryTokenStore
    from app.main import app

    app.state.token_store = InMemoryTokenStore()


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
    """AsyncSession por test, AISLADA por una transacción externa siempre revertida.

    Patrón "session joined into an external transaction" con savepoint (SQLAlchemy
    2.0 ``join_transaction_mode="create_savepoint"``): se abre UNA transacción sobre
    una conexión dedicada y la sesión del test corre DENTRO de un savepoint. Un
    ``session.commit()`` del endpoint (o del test) commitea el SAVEPOINT, no la
    transacción externa; al final se hace ``rollback`` de la externa y se descarta
    TODO —incluidos los commits—, sin limpieza manual por test.

    Por qué importa: el fixture viejo hacía un ``rollback`` ingenuo de una sesión sin
    transacción externa, así que NO distinguía ``flush`` de ``commit`` — un endpoint
    mutante que se olvidaba el ``commit`` igual pasaba los tests (la misma sesión veía
    el flush) pero NO persistía en prod, y un ``commit`` de verdad filtraba filas a la
    ``ynara_test`` compartida. Con el savepoint, los endpoints commitean como en prod
    y el aislamiento entre tests se mantiene intacto.
    """
    async with db_engine.connect() as conn:
        external = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await external.rollback()
