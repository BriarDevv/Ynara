"""Tests de VALOR de ``AdminMetricsService.moat`` + el helper ``_delta`` (TESTS-001/002).

Las métricas del panel admin estaban solo smoke-testeadas (200 sin sembrar datos): un
bug en los ~16 agregados de ``moat()`` (counts por capa, salud procedural, backlog de
consolidación) o en la matemática de ``_delta`` pasaba inadvertido. Estos tests asertan
VALORES — la red de seguridad para colapsar las queries seriales (SCAL-04) sin cambiar
resultados.

``moat()`` cuenta GLOBAL (cross-user); la DB de tests puede tener filas pre-existentes,
así que se asierta por INCREMENTO (``after - before``), no por valor absoluto. El
``_delta`` (puro) se testea unit, sin DB.

Tablas SAGRADAS (memoria): se INSERTA/lee vía ORM directo (read-only en el service),
NUNCA se descifra ``content``/``summary`` (las métricas son COUNT/metadata, regla #4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode
from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.services.admin_metrics import AdminMetricsService, _delta

_ZERO_VEC = [0.0] * 1024


# ---------------------------------------------------------------------------
# Unit: _delta (matemática del delta, sin DB)
# ---------------------------------------------------------------------------


def test_delta_growth_from_zero_is_up_100() -> None:
    """Crecer desde 0 (sin período anterior) -> ``up`` 100% (sin división por cero)."""
    d = _delta(current=5, previous=0)
    assert d.direction == "up"
    assert d.pct == 100.0


def test_delta_zero_to_zero_is_flat() -> None:
    """0 actual y 0 anterior -> ``flat`` 0% (dato honesto, sin inventar crecimiento)."""
    d = _delta(current=0, previous=0)
    assert d.direction == "flat"
    assert d.pct == 0.0


def test_delta_increase_and_decrease() -> None:
    """Subas/bajas porcentuales redondeadas a 1 decimal con la dirección correcta."""
    assert _delta(current=15, previous=10).direction == "up"
    assert _delta(current=15, previous=10).pct == 50.0
    assert _delta(current=8, previous=10).direction == "down"
    assert _delta(current=8, previous=10).pct == -20.0
    assert _delta(current=10, previous=10).direction == "flat"


# ---------------------------------------------------------------------------
# Integración: moat() counts / salud / backlog por INCREMENTO
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(
    session: AsyncSession, *, user_id: uuid.UUID, ended: bool = False
) -> ChatSession:
    cs = ChatSession(
        user_id=user_id,
        mode=Mode.VIDA,
        ended_at=datetime.now(UTC) if ended else None,
    )
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _seed_semantic(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    session.add(SemanticMemory(user_id=user_id, content=b"\x00" * 16, content_embedding=_ZERO_VEC))
    await session.flush()


async def _seed_episodic(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    cs = await _seed_session(session, user_id=user_id)
    session.add(
        EpisodicMemory(
            user_id=user_id,
            session_id=cs.id,
            summary=b"\x00" * 16,
            summary_embedding=_ZERO_VEC,
            is_sensitive=False,
            retention_days=365,
            occurred_at=datetime.now(UTC),
            topics={},
        )
    )
    await session.flush()


async def _seed_procedural(
    session: AsyncSession, *, user_id: uuid.UUID, key: str, stale: bool, confidence: float
) -> None:
    session.add(
        ProceduralMemory(
            user_id=user_id,
            key=key,
            value={"v": key},
            confidence=confidence,
            last_reinforced_at=datetime.now(UTC),
            stale=stale,
        )
    )
    await session.flush()


@pytest.mark.integration
async def test_moat_counts_health_backlog_increment(db_session: AsyncSession) -> None:
    """``moat()`` refleja exactamente lo sembrado: +2/+2/+3 counts, +1 stale, +1 backlog."""
    svc = AdminMetricsService(db_session)
    before = await svc.moat("7d")

    user = await _seed_user(db_session)
    await _seed_semantic(db_session, user_id=user.id)
    await _seed_semantic(db_session, user_id=user.id)
    await _seed_episodic(db_session, user_id=user.id)
    await _seed_episodic(db_session, user_id=user.id)
    await _seed_procedural(db_session, user_id=user.id, key="a", stale=False, confidence=0.9)
    await _seed_procedural(db_session, user_id=user.id, key="b", stale=False, confidence=0.5)
    await _seed_procedural(db_session, user_id=user.id, key="c", stale=True, confidence=0.1)
    # 1 sesión cerrada SIN episodic -> backlog (las sesiones de los episodios SÍ tienen).
    await _seed_session(db_session, user_id=user.id, ended=True)

    after = await svc.moat("7d")

    assert after.counts.semantic == before.counts.semantic + 2
    assert after.counts.episodic == before.counts.episodic + 2
    assert after.counts.procedural == before.counts.procedural + 3
    assert after.procedural.stale_count == before.procedural.stale_count + 1
    assert after.procedural.healthy_count == before.procedural.healthy_count + 2
    assert after.consolidation.backlog == before.consolidation.backlog + 1
