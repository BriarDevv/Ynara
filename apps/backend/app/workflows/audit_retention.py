"""Worker de retention del ``audit_log`` (24 meses, MEMORY.md / ``app/models/audit.py``).

``audit_log`` crece monótonamente: cada op de memoria consolidada inserta una
fila (issue #158) y nada las borra salvo el ``ON DELETE CASCADE`` al eliminar al
usuario. Este worker es la "vía normal de retention para usuarios activos" que el
modelo documenta: borra las entradas más viejas que ``AUDIT_RETENTION_DAYS``.

Reglas (regla #3 de ``AGENTS.md`` + perímetro regla #4):

1. ``DELETE`` SQL directo sobre la tabla SAGRADA ``audit_log``. Está permitido:
   la inmutabilidad se enforcea SOLO contra UPDATE (trigger
   ``trg_audit_log_block_update``); DELETE queda abierto a propósito para el
   cascade GDPR y para esta retention.
2. NO toca el SCHEMA: opera sobre la columna existente ``created_at``.
3. Job GLOBAL de mantenimiento: borra por tiempo, SIN filtro ``user_id``. No lee
   ni escribe data de un usuario para otro: solo aplica el paso del tiempo.
4. Mismo patrón Celery que ``decay.py``: task JSON-serializable + ``asyncio.run``
   + cuerpo ``_async_`` con ``session`` inyectable para tests + engine
   ``NullPool`` en prod + ``try/except`` que NO tumba el worker + logs SOLO de
   conteos (regla #4: nunca datos de usuario).

CUTOFF en Python (NO ``func.now()`` en el WHERE), igual que ``decay.py``: el test
siembra ``created_at`` relativo a un ``now`` conocido y el borrado es
determinista. ``timedelta(days=730)`` ≈ 24 meses (un par de días corto por
bisiestos: borra de MENOS, nunca de más — preferible para una tabla de auditoría).

CADENCIA (beat, decision documentada): mensual. Para una retention de 24 meses no
hace falta correr diario; mensual mantiene la tabla acotada sin scheduling
innecesario.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.models.audit import AuditLog
from app.workers.celery_app import celery_app
from app.workflows.consolidation import _normalize_db_url

logger = logging.getLogger(__name__)


# Retention de 24 meses (MEMORY.md / app/models/audit.py).
AUDIT_RETENTION_DAYS = 730


# ---------------------------------------------------------------------------
# Cuerpo async del purge (separado para inyección en tests)
# ---------------------------------------------------------------------------


async def _async_purge_audit(
    *,
    session: AsyncSession | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Borra las filas de ``audit_log`` más viejas que ``AUDIT_RETENTION_DAYS``.

    Retorna la cantidad de filas borradas. El cutoff se calcula en Python (no
    ``func.now()`` en el WHERE) para que los tests sean deterministas; ``now`` es
    inyectable por esa razón.

    Si ``session`` se inyecta (tests de integración) se usa directamente y NO se
    commitea (el fixture controla el rollback). Si es ``None`` (worker Celery en
    prod) se construye el engine con ``NullPool``, se commitea y se dispone el
    engine en ``finally`` (mismo patrón que ``decay.py``).
    """
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(days=AUDIT_RETENTION_DAYS)

    async def _run(db: AsyncSession) -> int:
        stmt = (
            sa_delete(AuditLog)
            .where(AuditLog.created_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        res = await db.execute(stmt)
        deleted = res.rowcount or 0
        await db.flush()
        return deleted

    if session is not None:
        # Modo test: sesión inyectada, NO commitear (rollback del fixture).
        return await _run(session)

    # Modo producción: engine con NullPool, commit + dispose.
    cfg = settings or get_settings()
    db_url = _normalize_db_url(cfg.database_url)
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with maker() as db_session:
            deleted = await _run(db_session)
            await db_session.commit()
        return deleted
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Task Celery — sin argumentos (job global), JSON-serializable
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="workflows.purge_audit_log")
def purge_audit_log(self) -> None:  # bind=True, self no se usa (sin retry)
    """Task Celery: borra las entradas de ``audit_log`` más viejas que 24 meses.

    Job GLOBAL de mantenimiento, sin argumentos (purga por tiempo, no por
    usuario). El cuerpo async corre con ``asyncio.run`` (worker prefork). Todo va
    en ``try/except``: un fallo NO tumba el worker y se loguea SOLO el conteo, SIN
    datos de usuario (regla #4).
    """
    try:
        deleted = asyncio.run(_async_purge_audit())
        logger.info("purge_audit_log: deleted=%d", deleted)
    except Exception:
        # Regla: el worker NUNCA muere por un fallo de retention.
        # Log técnico sin datos de usuario (regla #4).
        logger.exception("purge_audit_log: fallo al purgar audit_log (sin datos de usuario)")
