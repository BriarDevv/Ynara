"""Worker de retention de ``episodic_memory`` (ADR-007 D2 / roadmap §5.3).

``episodic_memory`` crece a medida que se cierran sesiones (el worker episodico
inserta un resumen por sesion). Cada fila lleva su propio ``retention_days``
(365 default, 180 si ``is_sensitive`` — modo Bienestar, ADR-007 D2). Este worker
es la "via normal de retention": borra los episodios cuyo ``created_at +
retention_days`` ya paso. Sin el, los episodios vencidos vivirian para siempre.

Reglas (regla #3 de ``AGENTS.md`` + perimetro regla #4):

1. ``DELETE`` SQL directo sobre la tabla SAGRADA ``episodic_memory``. Esta
   permitido: ``EpisodicMemoryStore.delete``/``wipe`` ya borran (no hay trigger
   anti-DELETE como en ``audit_log``); este worker hace el mismo borrado fisico,
   global y por tiempo.
2. NO toca el SCHEMA: la expiracion se computa en SQL sobre columnas existentes
   (``created_at`` + ``retention_days``), sin columna ``expires_at`` nueva ->
   sin migracion.
3. Job GLOBAL de mantenimiento: borra por tiempo, SIN filtro ``user_id`` (igual
   que ``purge_audit_log``). No lee ni descifra el ``summary`` (regla #4: solo
   viajan conteos); borrar el ``BYTEA`` no requiere leerlo en claro.
4. Conteo DIFERENCIADO ``is_sensitive`` (roadmap §5.3): se hacen DOS ``DELETE``
   disjuntos (sensible / no-sensible) para loguear cada conteo por separado. Los
   episodios sensibles (Bienestar) son los mas privados; tener su conteo de
   borrado aparte es la base de la "auditoria diferenciada" del §5.3. NO se escribe
   una fila en ``audit_log`` por borrado (decision deliberada, igual que
   ``purge_audit_log`` que no se auto-audita): la traza operativa es el log
   diferenciado de conteos. Una auditoria persistente per-row del borrado sensible
   (que sobreviva a la rotacion de logs, p.ej. para Ley 25.326) queda como
   refinamiento futuro de ADR-007, fuera del scope de este worker.
5. Mismo patron Celery que ``audit_retention.py`` / ``decay.py``: task
   JSON-serializable + ``asyncio.run`` + cuerpo ``_async_`` con ``session``
   inyectable para tests + engine ``NullPool`` en prod + ``try/except`` que NO
   tumba el worker + logs SOLO de conteos (regla #4: nunca datos de usuario).

EXPIRACION per-row en SQL (NO un cutoff unico en Python como ``audit_retention``,
porque ``retention_days`` varia por fila): el predicado es
``created_at + retention_days * interval '1 day' < now`` (ver ``_expired_predicate``).
``now`` se inyecta para que los tests sean deterministas. Predicado ``<`` ESTRICTO:
un episodio exacto en el borde de su ventana queda (guarda contra una regresion
``<`` -> ``<=``).

CADENCIA (beat): ``episodic_retention_interval_days`` de ``ynara.config.json
[memory]`` (default 1 = diario, configurable; ver ``RetentionConfig``).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, literal_column
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.memory import EpisodicMemory
from app.workers.celery_app import celery_app
from app.workflows._engine import worker_session

logger = logging.getLogger(__name__)


def _expired_predicate(now: datetime) -> ColumnElement[bool]:
    """``True`` para los episodios cuya ventana de retention ya venció.

    ``created_at + retention_days * interval '1 day' < now``, computado en SQL por
    fila (``retention_days`` varia: 365 default / 180 sensible). Se usa
    ``retention_days * interval '1 day'`` (no ``make_interval`` posicional) para que
    el mapeo dia-a-dia sea EXPLICITO y no dependa de contar argumentos en una ruta de
    borrado destructivo. Aritmetica de DIAS (no meses/anios): el offset es siempre
    exacto (``retention_days`` * 86400s), sin drift de calendario. Predicado ``<``
    ESTRICTO: el borde exacto queda (guarda contra una regresion ``<`` -> ``<=``).
    """
    return (
        EpisodicMemory.created_at
        + EpisodicMemory.retention_days * literal_column("interval '1 day'")
        < now
    )


async def _async_purge_episodic(
    *,
    session: AsyncSession | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Borra los episodios vencidos. Retorna ``(sensibles, no_sensibles)`` borrados.

    Dos ``DELETE`` disjuntos (``is_sensitive`` true/false) para conteo diferenciado
    (roadmap §5.3). El cutoff per-row se computa en SQL (ver ``_expired_predicate``);
    ``now`` es inyectable para tests deterministas.

    Si ``session`` se inyecta (tests de integracion) se usa directamente y NO se
    commitea (el fixture controla el rollback). Si es ``None`` (worker Celery en
    prod) se construye el engine con ``NullPool``, se commitea y se dispone el
    engine en ``finally`` (mismo patron que ``audit_retention.py`` / ``decay.py``).
    """
    current = now or datetime.now(UTC)
    expired = _expired_predicate(current)

    async def _run(db: AsyncSession) -> tuple[int, int]:
        # DELETE disjuntos: sensibles y no-sensibles por separado para contar cada
        # uno (§5.3). ``synchronize_session=False``: bulk delete sin sincronizar el
        # estado ORM en memoria (igual que audit_retention / wipe).
        # La disjuncion ``IS TRUE`` / ``IS FALSE`` cubre TODAS las filas porque
        # ``EpisodicMemory.is_sensitive`` es ``NOT NULL`` (default False); en logica
        # ternaria de SQL un ``NULL`` no matchearia ninguna y nunca se purgaria. Si
        # una migracion futura relajara esa nullability, este disjunto debe revisarse.
        sens = await db.execute(
            sa_delete(EpisodicMemory)
            .where(expired, EpisodicMemory.is_sensitive.is_(True))
            .execution_options(synchronize_session=False)
        )
        nons = await db.execute(
            sa_delete(EpisodicMemory)
            .where(expired, EpisodicMemory.is_sensitive.is_(False))
            .execution_options(synchronize_session=False)
        )
        await db.flush()
        return (sens.rowcount or 0, nons.rowcount or 0)

    if session is not None:
        # Modo test: sesion inyectada, NO commitear (rollback del fixture).
        return await _run(session)

    # Modo produccion: engine NullPool efimero; worker_session commitea al salir
    # del bloque y dispone el engine (mismo patron centralizado en _engine.py).
    cfg = settings or get_settings()
    async with worker_session(cfg) as db_session:
        return await _run(db_session)


@celery_app.task(bind=True, name="workflows.purge_episodic_memory")
def purge_episodic_memory(self) -> None:  # bind=True, self no se usa (sin retry)
    """Task Celery: borra los episodios cuya ventana de retention venció.

    Job GLOBAL de mantenimiento, sin argumentos (purga por tiempo, no por usuario).
    El cuerpo async corre con ``asyncio.run`` (worker prefork). Todo va en
    ``try/except``: un fallo NO tumba el worker y se loguean SOLO los conteos
    (sensible / no-sensible / total), SIN datos de usuario (regla #4).
    """
    try:
        sensitive, non_sensitive = asyncio.run(_async_purge_episodic())
        logger.info(
            "purge_episodic_memory: sensitive=%d non_sensitive=%d total=%d",
            sensitive,
            non_sensitive,
            sensitive + non_sensitive,
        )
    except Exception:
        # Regla: el worker NUNCA muere por un fallo de retention.
        # Log tecnico sin datos de usuario (regla #4).
        logger.exception(
            "purge_episodic_memory: fallo al purgar episodic_memory (sin datos de usuario)"
        )
