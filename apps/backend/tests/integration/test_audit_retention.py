"""Tests de INTEGRACIÓN del worker de retention del ``audit_log`` (tabla sagrada).

El test solo INSERTA/borra filas vía el worker; NUNCA modifica el modelo ni la
migración (regla #3). Corren contra el Postgres REAL vía ``db_session`` (savepoint
+ rollback al final). Requieren ``TEST_DATABASE_URL`` y el marker ``-m integration``.

Cubre que ``_async_purge_audit`` borra las entradas más viejas que
``AUDIT_RETENTION_DAYS`` y respeta las recientes. El ``now`` se inyecta para que el
cutoff sea determinista (mismo patrón que ``decay.py``). Que el DELETE funcione es
además la prueba de que el trigger de inmutabilidad (BEFORE UPDATE) NO bloquea
DELETE (la retention es una de sus dos vías legítimas).

NOTA (regla #4): el ``audit_log`` NO guarda texto de usuario; ningún test asierta
contenido de memoria, solo metadata + ``record_hash``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.user import User
from app.workflows.audit_retention import AUDIT_RETENTION_DAYS, _async_purge_audit

# ---------------------------------------------------------------------------
# Helpers de siembra
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y lo retorna (flush, no commit — rollback al final)."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_audit_row(session: AsyncSession, user: User, *, created_at: datetime) -> AuditLog:
    """Inserta una fila de ``audit_log`` con un ``created_at`` explícito.

    El ``created_at`` se setea a mano (override del ``server_default=func.now()``)
    para ubicar la fila a un lado u otro del cutoff de retention. El
    ``record_hash`` es un sha256 hex válido, sin texto de usuario (regla #4).
    """
    row = AuditLog(
        user_id=user.id,
        operation=AuditOperation.WRITE,
        target_layer=MemoryLayer.SEMANTIC,
        target_id=uuid.uuid4(),
        origin_model=LlmModel.QWEN,
        origin_mode=Mode.PRODUCTIVIDAD,
        origin_tool="memory.add",
        record_hash="a" * 64,
        sensitive=False,
        created_at=created_at,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _audit_exists(session: AsyncSession, audit_id: uuid.UUID) -> bool:
    """``True`` si la fila de ``audit_log`` con ese id existe en la DB."""
    stmt = select(AuditLog.id).where(AuditLog.id == audit_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 1. Borra lo viejo, respeta lo reciente
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_purge_deletes_rows_older_than_retention(db_session: AsyncSession) -> None:
    """``_async_purge_audit`` borra las filas > retention y conserva las recientes."""
    now = datetime.now(UTC)
    user = await _seed_user(db_session)
    old = await _seed_audit_row(
        db_session, user, created_at=now - timedelta(days=AUDIT_RETENTION_DAYS + 30)
    )
    recent = await _seed_audit_row(db_session, user, created_at=now - timedelta(days=10))

    deleted = await _async_purge_audit(session=db_session, now=now)

    assert deleted == 1, "solo la fila vieja debe borrarse"
    assert await _audit_exists(db_session, old.id) is False, "la fila vieja se purga"
    assert await _audit_exists(db_session, recent.id) is True, "la reciente queda"


# ---------------------------------------------------------------------------
# 2. El borde de la ventana queda dentro (no se purga)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_purge_keeps_rows_within_retention(db_session: AsyncSession) -> None:
    """Filas dentro de la ventana NO se borran, incluida la del borde EXACTO.

    El predicado es ``created_at < cutoff`` (estricto): una fila sembrada exacto en
    el cutoff (``now - AUDIT_RETENTION_DAYS``) queda — es la guarda contra una
    regresión ``<`` → ``<=``.
    """
    now = datetime.now(UTC)
    user = await _seed_user(db_session)
    just_inside = await _seed_audit_row(
        db_session, user, created_at=now - timedelta(days=AUDIT_RETENTION_DAYS - 1)
    )
    at_cutoff = await _seed_audit_row(
        db_session, user, created_at=now - timedelta(days=AUDIT_RETENTION_DAYS)
    )

    deleted = await _async_purge_audit(session=db_session, now=now)

    assert deleted == 0, "nada en o dentro de la ventana de retention se borra"
    assert await _audit_exists(db_session, just_inside.id) is True
    assert await _audit_exists(db_session, at_cutoff.id) is True
