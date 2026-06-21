"""Bootstrap del engine de DB para los workers Celery (DRY del patrón NullPool).

Cada task corre su cuerpo async con ``asyncio.run()`` en un worker prefork, que
crea un event loop NUEVO por invocación. Las conexiones asyncpg quedan atadas a su
loop, así que NO se pueden reusar entre tasks → ``NullPool`` es obligatorio (sin él,
reusar una conexión entre loops distintos da 'Future attached to a different loop',
decisión #4 de la consolidación).

Este módulo centraliza esa decisión, que antes estaba duplicada en los 4 workflows
(consolidation/decay/audit_retention/episodic_retention) y que además importaban el
privado ``_normalize_db_url`` de ``consolidation`` cross-module. Cambiar la política
de pooling de los workers ahora toca un solo lugar.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def normalize_db_url(url: str) -> str:
    """Normaliza la URL de DB al dialect asyncpg (``postgresql://`` → ``postgresql+asyncpg://``)."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@asynccontextmanager
async def worker_session(settings: Settings) -> AsyncIterator[AsyncSession]:
    """Engine ``NullPool`` efímero + ``AsyncSession`` para el cuerpo de un task Celery.

    Construye el engine con ``NullPool`` (obligatorio en prefork, ver el módulo), abre
    una sesión, commitea al salir LIMPIO del bloque ``async with`` y dispone el engine
    SIEMPRE (``finally``). Si el bloque levanta, la sesión hace rollback (su propio
    context manager) y el commit se saltea; el engine se dispone igual.

    Reemplaza el patrón duplicado en los workers
    (``create_async_engine(NullPool)`` + ``async_sessionmaker`` + ``commit`` +
    ``dispose`` en ``finally``). El cuerpo del worker hace su trabajo dentro del
    ``async with`` y NO commitea: el commit lo da este context manager al salir.

    Limitación conocida (SIGALRM): si Celery dispara ``SoftTimeLimitExceeded``
    (``task_soft_time_limit``), la señal puede interrumpir el ``finally`` antes del
    ``dispose()``. Es aceptable: ``NullPool`` no mantiene un pool que drenar (cada
    task abre y cierra su única conexión), y Postgres reclama la conexión huérfana al
    detectar el cierre del socket. No hay fuga de pool por este camino.
    """
    engine = create_async_engine(normalize_db_url(settings.database_url), poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with maker() as session:
            yield session
            await session.commit()
    finally:
        await engine.dispose()
