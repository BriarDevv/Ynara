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
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings

if TYPE_CHECKING:
    from app.models.base import Base


# Filas por lote en los DELETE de retention (WW-01). Acota cada transacción: un
# backlog grande se purga en N lotes commiteados, no en una única transacción que el
# ``task_time_limit`` de Celery rollbackearía entera. 1000 mantiene cada lote corto.
DELETE_BATCH_SIZE = 1000


async def delete_in_batches(
    session: AsyncSession,
    model: type[Base],
    where: ColumnElement[bool],
    *,
    batch_size: int = DELETE_BATCH_SIZE,
    commit: bool,
) -> int:
    """Borra en lotes las filas de ``model`` que matchean ``where``. Devuelve el total.

    Por qué en lotes (auditoría WW-01): un único ``DELETE`` de un backlog grande puede
    chocar con el ``task_time_limit`` de Celery y ROLLBACKEAR TODO → 0 filas purgadas +
    un loop de fallo en cada corrida. Con commit por lote, un kill por time-limit
    preserva los lotes ya commiteados (progreso real) y el próximo run continúa donde
    quedó.

    ``commit=True`` (prod): commitea cada lote. ``commit=False`` (test con la sesión
    inyectada del fixture savepoint): solo ``flush()`` → el rollback del fixture descarta
    todo, pero el loop igual TERMINA (los deletes flusheados ya no matchean dentro de la
    misma transacción). ``synchronize_session=False``: bulk delete sin sincronizar el
    estado ORM en memoria (igual que los DELETE originales de los workers).

    Borra por PK (``model.id``, UUIDPKMixin) vía subquery ``id IN (SELECT id ... LIMIT
    n)``: el ``LIMIT`` acota el lote; ``where`` se reevalúa una vez por lote sobre el
    estado ya purgado, así el loop converge.
    """
    pk = model.id
    total = 0
    while True:
        batch_ids = select(pk).where(where).limit(batch_size)
        res = await session.execute(
            sa_delete(model).where(pk.in_(batch_ids)).execution_options(synchronize_session=False)
        )
        deleted = res.rowcount or 0
        total += deleted
        if commit:
            await session.commit()
        else:
            await session.flush()
        if deleted < batch_size:
            break
    return total


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
