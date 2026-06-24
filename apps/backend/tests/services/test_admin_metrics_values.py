"""Tests de VALOR EXACTO de ``AdminMetricsService`` (red de seguridad de SCAL-04).

``overview()`` y ``moat()`` cuentan GLOBAL cross-user. Para asertar valores EXACTOS
(incluidos los deltas cur/prev) se limpian las tablas al inicio del test con un
``DELETE FROM users`` (cascada a sesiones/memoria/audit) DENTRO del savepoint del
fixture: el rollback del fixture restaura las filas pre-existentes, así que no se borra
nada de verdad, pero durante el test las métricas ven SOLO lo sembrado.

Esto es la red de seguridad para colapsar las queries seriales de ``overview``/``moat``
(SCAL-04, ``COUNT(*) FILTER (WHERE ...)`` en vez de N queries) garantizando que los
totales, los conteos por ventana y los deltas no cambian.

Read-only sobre tablas sagradas (COUNT/metadata, regla #4: nunca descifra).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.services.admin_metrics import AdminMetricsService

pytestmark = pytest.mark.integration

_ZERO_VEC = [0.0] * 1024


async def _clear_all(session: AsyncSession) -> None:
    """Vacía las tablas que tocan las métricas (DELETE users -> cascada), dentro del savepoint."""
    await session.execute(sa_delete(User))
    await session.flush()


async def _user(session: AsyncSession) -> User:
    user = User(is_ephemeral=False)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _session_row(
    session: AsyncSession, *, user_id: uuid.UUID, started_at: datetime, ended: bool = False
) -> ChatSession:
    cs = ChatSession(
        user_id=user_id,
        mode=Mode.VIDA,
        started_at=started_at,
        ended_at=datetime.now(UTC) if ended else None,
    )
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _semantic(session: AsyncSession, *, user_id: uuid.UUID, created_at: datetime) -> None:
    session.add(
        SemanticMemory(
            user_id=user_id,
            content=b"\x00" * 16,
            content_embedding=_ZERO_VEC,
            created_at=created_at,
        )
    )
    await session.flush()


async def _episodic(session: AsyncSession, *, user_id: uuid.UUID, created_at: datetime) -> None:
    cs = await _session_row(session, user_id=user_id, started_at=created_at)
    session.add(
        EpisodicMemory(
            user_id=user_id,
            session_id=cs.id,
            summary=b"\x00" * 16,
            summary_embedding=_ZERO_VEC,
            is_sensitive=False,
            retention_days=365,
            occurred_at=created_at,
            topics={},
            created_at=created_at,
        )
    )
    await session.flush()


async def _procedural(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key: str,
    created_at: datetime,
    stale: bool = False,
) -> None:
    session.add(
        ProceduralMemory(
            user_id=user_id,
            key=key,
            value={"v": key},
            confidence=0.5,
            last_reinforced_at=created_at,
            stale=stale,
            created_at=created_at,
        )
    )
    await session.flush()


async def _audit(session: AsyncSession, *, user_id: uuid.UUID, created_at: datetime) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
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
    )
    await session.flush()


async def test_moat_exact_counts_and_deltas(db_session: AsyncSession) -> None:
    """``moat()`` con tablas limpias: counts totales y deltas cur/prev EXACTOS."""
    now = datetime.now(UTC)
    cur = now - timedelta(days=1)  # ventana actual [now-7d, now)
    prev = now - timedelta(days=10)  # ventana anterior [now-14d, now-7d)

    await _clear_all(db_session)
    user = await _user(db_session)

    # semantic: 3 actual + 1 anterior -> total 4, delta _delta(3,1) = up 200%.
    for _ in range(3):
        await _semantic(db_session, user_id=user.id, created_at=cur)
    await _semantic(db_session, user_id=user.id, created_at=prev)
    # episodic: 2 actual + 2 anterior -> total 4, delta _delta(2,2) = flat 0%.
    for _ in range(2):
        await _episodic(db_session, user_id=user.id, created_at=cur)
    for _ in range(2):
        await _episodic(db_session, user_id=user.id, created_at=prev)
    # procedural: 1 actual (stale) + 0 anterior -> total 1, delta up 100%.
    await _procedural(db_session, user_id=user.id, key="p", created_at=cur, stale=True)

    moat = await AdminMetricsService(db_session).moat("7d")

    # Counts totales (ignoran ventana).
    assert moat.counts.semantic == 4
    assert moat.counts.episodic == 4
    assert moat.counts.procedural == 1

    # Deltas cur vs prev (el corazón de lo que colapsa SCAL-04).
    assert (moat.deltas.semantic.direction, moat.deltas.semantic.pct) == ("up", 200.0)
    assert (moat.deltas.episodic.direction, moat.deltas.episodic.pct) == ("flat", 0.0)
    assert (moat.deltas.procedural.direction, moat.deltas.procedural.pct) == ("up", 100.0)

    # Salud procedural.
    assert moat.procedural.stale_count == 1
    assert moat.procedural.healthy_count == 0


async def test_overview_exact_kpis(db_session: AsyncSession) -> None:
    """``overview()`` con tablas limpias: KPIs (total + delta) EXACTOS por dominio."""
    now = datetime.now(UTC)
    cur = now - timedelta(days=1)
    prev = now - timedelta(days=10)

    await _clear_all(db_session)

    # 2 users creados en la ventana actual (created_at = ahora, via _user) + nada antes.
    user_a = await _user(db_session)
    user_b = await _user(db_session)

    # sessions: 3 actual + 1 anterior -> cur 3, prev 1.
    for _ in range(3):
        await _session_row(db_session, user_id=user_a.id, started_at=cur)
    await _session_row(db_session, user_id=user_a.id, started_at=prev)

    # memorias: 1 semantic + 1 episodic + 1 procedural, todas actuales -> total 3.
    await _semantic(db_session, user_id=user_a.id, created_at=cur)
    await _episodic(db_session, user_id=user_b.id, created_at=cur)
    await _procedural(db_session, user_id=user_b.id, key="k", created_at=cur)

    # audit: 2 actual + 1 anterior -> cur 2, prev 1.
    await _audit(db_session, user_id=user_a.id, created_at=cur)
    await _audit(db_session, user_id=user_a.id, created_at=cur)
    await _audit(db_session, user_id=user_a.id, created_at=prev)

    ov = await AdminMetricsService(db_session).overview("7d")

    # users_total = 2 (ambos creados ahora). prev (created_at < start) = 0 -> up 100%.
    assert ov.kpis.users_total.value == 2
    assert ov.kpis.users_total.delta.direction == "up"

    # sessions: cur 3 (incluye las 4 de las sesiones? cuidado: _episodic crea sesiones).
    # _episodic(user_b) creó 1 sesión en `cur`; las de overview son 3+1. Total sesiones
    # actuales = 3 (overview) + 1 (episodic) = 4. El KPI cuenta started_at >= start.
    assert ov.kpis.sessions.value == 4  # 3 sembradas + 1 de la episodic actual
    assert ov.kpis.sessions.delta.direction == "up"  # 4 vs 1 anterior

    # memorias_total = 3 (1 por capa).
    assert ov.kpis.memories.value == 3

    # audit: cur 2 vs prev 1 -> up.
    assert ov.kpis.audit_events.value == 2
    assert ov.kpis.audit_events.delta.direction == "up"
