"""Worker de decay de memoria procedural (M8 Ola 3, ADR-007 D1).

Mecanismo de 'olvido': las preferencias que dejan de reforzarse pierden
confianza y eventualmente se borran. El router ya filtra ``stale=False`` al
inyectar contexto, asi una entrada stale deja de influir sin borrarse todavia.

Reglas no negociables (ADR-007 D1 + regla #3 de ``AGENTS.md``):

1. Opera sobre la tabla SAGRADA ``procedural_memory`` con UPDATE/DELETE SQL
   DIRECTO (``update()`` / ``delete()`` sobre el modelo). NUNCA via
   ``ProceduralMemoryStore.upsert``: ese resetea ``confidence=1.0`` /
   ``last_reinforced_at=now()`` / ``stale=false`` (reforzar), lo opuesto al
   decay. Reforzar es responsabilidad del store (consolidacion), NO del decay.
2. NO toca el SCHEMA: opera sobre columnas existentes (``confidence``,
   ``last_reinforced_at``, ``stale``). Sin migracion nueva.
3. Job GLOBAL de mantenimiento: decae TODAS las entradas elegibles por tiempo,
   sin filtro ``user_id``. No lee ni escribe data de un usuario para otro: solo
   aplica el paso del tiempo. El aislamiento por usuario no aplica.
4. Mismo patron Celery que ``consolidation.py``: task JSON-serializable +
   ``asyncio.run`` + cuerpo ``_async_`` con ``session`` inyectable para tests +
   engine ``NullPool`` en prod + ``try/except`` que NO tumba el worker + logs
   SIN datos de usuario (regla #4): solo conteos.

CADENCIA (decision M8 Ola 3, documentada): para que ``confidence *= 0.9 por
intervalo`` NO se componga dia a dia (y sin agregar una columna
``last_decayed_at``, que seria migracion sagrada), el beat corre cada
``DECAY_INTERVAL_DAYS`` dias, NO diario. Cada corrida decae las entradas no
reforzadas en el ultimo intervalo. ADR-007 dice 'diario', pero sin columna de
tracking la cadencia por-intervalo es la unica forma correcta sin compounding
ni migracion.

CUTOFF en Python: el WHERE compara ``last_reinforced_at`` contra un cutoff
calculado en Python con ``datetime.now(UTC) - timedelta(...)`` (NO ``func.now()``
en el WHERE), asi los tests siembran ``last_reinforced_at`` relativo a un now
conocido y el comportamiento es determinista.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.models.memory import ProceduralMemory
from app.workers.celery_app import celery_app
from app.workflows.consolidation import _normalize_db_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de decay (ADR-007 D1 defaults)
# TODO: mover a ynara.config.json[memory] cuando se agregue ese bloque de
# parametros (tocar ynara.config.json ahora es gate regla #1).
# ---------------------------------------------------------------------------

DECAY_INTERVAL_DAYS = 14
DECAY_FACTOR = 0.9
STALE_THRESHOLD = 0.3
HARD_DELETE_THRESHOLD = 0.1
HARD_DELETE_MIN_DAYS = 90


@dataclass(frozen=True)
class DecayResult:
    """Reporte de una corrida de decay (solo conteos, sin datos de usuario).

    ``staled`` cuenta las entradas marcadas stale EN ESTA corrida (transiciones
    ``False -> True`` al momento de marcar). Como el paso (c) puede hard-deletear
    algunas de esas mismas filas (toda ``confidence < 0.1`` es tambien ``< 0.3``),
    ``staled`` puede incluir filas que ya no existen al terminar: es una metrica
    de observabilidad del paso (b), no un conteo del estado final.
    """

    decayed: int
    staled: int
    deleted: int


# ---------------------------------------------------------------------------
# Cuerpo async del decay (separado para inyeccion en tests)
# ---------------------------------------------------------------------------


async def _async_decay(
    *,
    session: AsyncSession | None = None,
    settings: Settings | None = None,
) -> DecayResult:
    """Nucleo async del decay procedural; retorna los conteos de cada paso.

    Tres pasos EN ORDEN, cada uno UPDATE/DELETE SQL directo sobre la tabla
    sagrada ``procedural_memory``:

    (a) DECAY: a toda entrada cuyo ``last_reinforced_at`` quedo por debajo del
        cutoff (no reforzada en el ultimo intervalo) se le aplica
        ``confidence *= DECAY_FACTOR``. ``0.9 * confidence`` nunca viola el
        CheckConstraint ``confidence BETWEEN 0 AND 1``.
    (b) STALE: toda entrada con ``confidence < STALE_THRESHOLD`` que aun no
        este marcada queda ``stale=True`` (el router filtra ``stale=False``).
    (c) HARD DELETE: borrado fisico cuando ``confidence < HARD_DELETE_THRESHOLD``
        Y ``last_reinforced_at`` mas viejo que ``HARD_DELETE_MIN_DAYS``. Doble
        criterio: evita borrar entradas que decayeron por baja interaccion
        general reciente.

    Si ``session`` se inyecta (tests de integracion) se usa directamente y NO se
    commitea (el fixture controla el rollback); se hace ``flush()`` entre pasos
    para que cada UPDATE/DELETE vea los efectos del anterior. Si es ``None``
    (worker Celery en prod) se construye el engine con ``NullPool``, se abre la
    sesion, se commitea y se dispone el engine en ``finally``.
    """
    now = datetime.now(UTC)
    decay_cutoff = now - timedelta(days=DECAY_INTERVAL_DAYS)
    hard_delete_cutoff = now - timedelta(days=HARD_DELETE_MIN_DAYS)

    async def _run(db: AsyncSession) -> DecayResult:
        # (a) DECAY — confidence *= 0.9 a las no reforzadas en el ultimo intervalo.
        decay_stmt = (
            sa_update(ProceduralMemory)
            .where(ProceduralMemory.last_reinforced_at < decay_cutoff)
            .values(confidence=ProceduralMemory.confidence * DECAY_FACTOR)
            .execution_options(synchronize_session=False)
        )
        decay_res = await db.execute(decay_stmt)
        decayed = decay_res.rowcount or 0
        await db.flush()

        # (b) STALE — marcar stale las que cayeron bajo el umbral (idempotente:
        # solo las que aun no estan stale, asi el conteo refleja transiciones).
        stale_stmt = (
            sa_update(ProceduralMemory)
            .where(
                ProceduralMemory.confidence < STALE_THRESHOLD,
                ProceduralMemory.stale.is_(False),
            )
            .values(stale=True)
            .execution_options(synchronize_session=False)
        )
        stale_res = await db.execute(stale_stmt)
        staled = stale_res.rowcount or 0
        await db.flush()

        # (c) HARD DELETE — doble criterio: muy baja confianza Y muy vieja.
        delete_stmt = (
            sa_delete(ProceduralMemory)
            .where(
                ProceduralMemory.confidence < HARD_DELETE_THRESHOLD,
                ProceduralMemory.last_reinforced_at < hard_delete_cutoff,
            )
            .execution_options(synchronize_session=False)
        )
        delete_res = await db.execute(delete_stmt)
        deleted = delete_res.rowcount or 0
        await db.flush()

        return DecayResult(decayed=decayed, staled=staled, deleted=deleted)

    if session is not None:
        # Modo test: usar la sesion inyectada, NO commitear (rollback del fixture).
        return await _run(session)

    # Modo produccion: engine con NullPool (decision #4), commit + dispose.
    cfg = settings or get_settings()
    db_url = _normalize_db_url(cfg.database_url)
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with maker() as db_session:
            result = await _run(db_session)
            await db_session.commit()
        return result
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Task Celery — sin argumentos (job global), JSON-serializable
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="workflows.decay_procedural")
def decay_procedural(self) -> None:  # bind=True, self no se usa (sin retry en M8)
    """Task Celery: aplica decay/stale/hard-delete a la memoria procedural.

    Job GLOBAL de mantenimiento, sin argumentos (decae por tiempo, no por
    usuario). El cuerpo async corre con ``asyncio.run`` (worker prefork). Todo
    el bloque va en ``try/except``: un fallo NO tumba el worker y se loguea solo
    los conteos, SIN datos de usuario (regla #4).
    """
    try:
        result = asyncio.run(_async_decay())
        logger.info(
            "decay_procedural: decayed=%d staled=%d deleted=%d",
            result.decayed,
            result.staled,
            result.deleted,
        )
    except Exception:
        # Regla: el worker NUNCA muere por un fallo de decay.
        # Log tecnico sin datos de usuario (regla #4).
        logger.exception("decay_procedural: fallo al aplicar decay (sin datos de usuario)")
