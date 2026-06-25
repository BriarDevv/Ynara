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


async def _mode_session(
    session: AsyncSession, *, user_id: uuid.UUID, mode: Mode, started_at: datetime
) -> ChatSession:
    """Sesión ABIERTA con ``mode`` explícito (para asertar el group_by de mode_mix)."""
    cs = ChatSession(user_id=user_id, mode=mode, started_at=started_at, ended_at=None)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _closed_session(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    mode: Mode,
    started_at: datetime,
    ended_at: datetime,
) -> ChatSession:
    """Sesión CERRADA con ``started_at``/``ended_at`` explícitos (para asertar avg_minutes)."""
    cs = ChatSession(user_id=user_id, mode=mode, started_at=started_at, ended_at=ended_at)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _procedural_conf(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key: str,
    confidence: float,
    created_at: datetime,
) -> None:
    """Procedural con ``confidence`` explícito (para asertar el histograma width_bucket)."""
    session.add(
        ProceduralMemory(
            user_id=user_id,
            key=key,
            value={"v": key},
            confidence=confidence,
            last_reinforced_at=created_at,
            stale=False,
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


async def test_overview_sessions_spark_exact_series(db_session: AsyncSession) -> None:
    """``overview().sessions_series`` (``_daily_series``): conteo EXACTO por día + ceros."""
    now = datetime.now(UTC)
    # Dos días bien dentro de la ventana [now-7d, now), lejos de los bordes (mediodía) para
    # que el date_trunc('day') no se corra por la zona horaria.
    day_a = now - timedelta(days=3, hours=12)
    day_b = now - timedelta(days=1, hours=12)

    await _clear_all(db_session)
    user = await _user(db_session)

    # 3 sesiones en day_a + 2 en day_b. NO uso _episodic (crea sesiones fantasma).
    for _ in range(3):
        await _session_row(db_session, user_id=user.id, started_at=day_a)
    for _ in range(2):
        await _session_row(db_session, user_id=user.id, started_at=day_b)

    ov = await AdminMetricsService(db_session).overview("7d")
    series = {p.date: p.value for p in ov.sessions_series}

    # La serie cubre 8 días (start.date()..now.date() inclusive) y suma exactamente 5.
    assert len(ov.sessions_series) == 8
    assert sum(p.value for p in ov.sessions_series) == 5
    # Los dos días sembrados tienen su conteo exacto; el resto son ceros rellenados.
    assert series[day_a.date().isoformat()] == 3
    assert series[day_b.date().isoformat()] == 2
    zero_days = [
        p.value
        for p in ov.sessions_series
        if p.date not in {day_a.date().isoformat(), day_b.date().isoformat()}
    ]
    assert zero_days == [0] * 6


async def test_overview_mode_mix_exact_group_by(db_session: AsyncSession) -> None:
    """``overview().mode_mix`` (group_by mode): conteo EXACTO de sesiones por modo en la ventana."""
    now = datetime.now(UTC)
    cur = now - timedelta(days=1)
    prev = now - timedelta(days=10)  # FUERA de la ventana: no debe contar.

    await _clear_all(db_session)
    user = await _user(db_session)

    # 3 PRODUCTIVIDAD + 2 ESTUDIO + 1 VIDA dentro de la ventana.
    for _ in range(3):
        await _mode_session(db_session, user_id=user.id, mode=Mode.PRODUCTIVIDAD, started_at=cur)
    for _ in range(2):
        await _mode_session(db_session, user_id=user.id, mode=Mode.ESTUDIO, started_at=cur)
    await _mode_session(db_session, user_id=user.id, mode=Mode.VIDA, started_at=cur)
    # 1 ESTUDIO anterior: fuera de [start, now), no entra en el mix.
    await _mode_session(db_session, user_id=user.id, mode=Mode.ESTUDIO, started_at=prev)

    ov = await AdminMetricsService(db_session).overview("7d")
    mix = {row.mode: row.value for row in ov.mode_mix}

    assert mix == {Mode.PRODUCTIVIDAD: 3, Mode.ESTUDIO: 2, Mode.VIDA: 1}


async def test_overview_audit_preview_last_six_desc(db_session: AsyncSession) -> None:
    """``overview().audit_preview``: las ÚLTIMAS 6 entradas, ordenadas por created_at DESC."""
    now = datetime.now(UTC)

    await _clear_all(db_session)
    user = await _user(db_session)

    # 7 audits con created_at estrictamente creciente (t-7m ... t-1m). La más vieja (t-7m)
    # debe quedar AFUERA del preview (limit 6, order desc).
    times = [now - timedelta(minutes=m) for m in range(7, 0, -1)]
    for created in times:
        await _audit(db_session, user_id=user.id, created_at=created)

    ov = await AdminMetricsService(db_session).overview("7d")

    # Exactamente 6 filas, ordenadas DESC: la primera es la más reciente (t-1m).
    assert len(ov.audit_preview) == 6
    preview_times = [row.created_at for row in ov.audit_preview]
    assert preview_times == sorted(preview_times, reverse=True)
    assert preview_times[0] == times[-1]  # la más nueva (t-1m)
    assert preview_times[-1] == times[1]  # la 6ta más nueva (t-2m); t-7m quedó afuera
    assert times[0] not in preview_times  # la más vieja NO está


async def test_modes_avg_minutes_closed_only(db_session: AsyncSession) -> None:
    """``modes().duration[*].avg_minutes``: promedio de minutos SOLO de sesiones cerradas."""
    now = datetime.now(UTC)
    base = now - timedelta(days=2)  # dentro de [now-7d, now)

    await _clear_all(db_session)
    user = await _user(db_session)

    # ESTUDIO: 2 cerradas de 10 y 20 min -> avg 15.0. + 1 abierta (no pesa en el avg).
    await _closed_session(
        db_session,
        user_id=user.id,
        mode=Mode.ESTUDIO,
        started_at=base,
        ended_at=base + timedelta(minutes=10),
    )
    await _closed_session(
        db_session,
        user_id=user.id,
        mode=Mode.ESTUDIO,
        started_at=base,
        ended_at=base + timedelta(minutes=20),
    )
    await _mode_session(db_session, user_id=user.id, mode=Mode.ESTUDIO, started_at=base)
    # VIDA: 1 cerrada de 30 min -> avg 30.0.
    await _closed_session(
        db_session,
        user_id=user.id,
        mode=Mode.VIDA,
        started_at=base,
        ended_at=base + timedelta(minutes=30),
    )

    modes = await AdminMetricsService(db_session).modes("7d")
    by_mode = {row.mode: row for row in modes.duration}

    # ESTUDIO: avg de {10, 20} = 15.0; 2 cerradas, 1 abierta.
    assert by_mode[Mode.ESTUDIO].avg_minutes == 15.0
    assert by_mode[Mode.ESTUDIO].closed_sessions == 2
    assert by_mode[Mode.ESTUDIO].open_sessions == 1
    # VIDA: avg de {30} = 30.0; 1 cerrada, 0 abiertas.
    assert by_mode[Mode.VIDA].avg_minutes == 30.0
    assert by_mode[Mode.VIDA].closed_sessions == 1
    assert by_mode[Mode.VIDA].open_sessions == 0


async def test_moat_confidence_histogram_width_bucket(db_session: AsyncSession) -> None:
    """``moat().procedural.confidence_buckets``: histograma EXACTO (width_bucket en 5 buckets)."""
    now = datetime.now(UTC)
    cur = now - timedelta(days=1)

    await _clear_all(db_session)
    user = await _user(db_session)

    # width_bucket(c, 0, 1, 5): bucket i cubre [(i-1)/5, i/5). El valor 1.0 cae en el
    # bucket 6 y el código lo suma al último (0.8-1.0).
    #   0.10 -> b1 (0.0-0.2)
    #   0.30, 0.35 -> b2 (0.2-0.4)
    #   0.55 -> b3 (0.4-0.6)
    #   (b4 vacío -> 0.6-0.8 = 0)
    #   0.90 -> b5, 1.00 -> b6 (sumado a 0.8-1.0) -> 0.8-1.0 = 2
    confidences = [0.10, 0.30, 0.35, 0.55, 0.90, 1.00]
    for idx, conf in enumerate(confidences):
        await _procedural_conf(
            db_session, user_id=user.id, key=f"k{idx}", confidence=conf, created_at=cur
        )

    moat = await AdminMetricsService(db_session).moat("7d")
    hist = {b.range: b.count for b in moat.procedural.confidence_buckets}

    assert hist == {
        "0.0-0.2": 1,
        "0.2-0.4": 2,
        "0.4-0.6": 1,
        "0.6-0.8": 0,
        "0.8-1.0": 2,  # 0.90 (b5) + 1.00 (b6 reasignado)
    }


async def test_users_active_window_start_vs_prev(db_session: AsyncSession) -> None:
    """``users().activity.dau``: usuarios activos (DISTINCT) en la ventana actual vs la previa."""
    now = datetime.now(UTC)
    # DAU = ventana de 1 día. current=[now-1d, now); previous=[now-2d, now-1d).
    in_current = now - timedelta(hours=6)  # dentro de [now-1d, now)
    in_previous = now - timedelta(hours=36)  # dentro de [now-2d, now-1d)

    await _clear_all(db_session)
    user_a = await _user(db_session)
    user_b = await _user(db_session)
    user_c = await _user(db_session)

    # Ventana actual: user_a (2 sesiones, cuenta 1 por DISTINCT) + user_b -> 2 activos.
    await _session_row(db_session, user_id=user_a.id, started_at=in_current)
    await _session_row(db_session, user_id=user_a.id, started_at=in_current)
    await _session_row(db_session, user_id=user_b.id, started_at=in_current)
    # Ventana previa: solo user_c -> 1 activo.
    await _session_row(db_session, user_id=user_c.id, started_at=in_previous)

    users = await AdminMetricsService(db_session).users("7d")

    # DAU current = 2 (a, b, distinct); previous = 1 (c) -> _delta(2, 1) = up 100%.
    assert users.activity.dau.value == 2
    assert (users.activity.dau.delta.direction, users.activity.dau.delta.pct) == ("up", 100.0)
