"""Panel admin interno: 6 GET de métricas read-only (``/v1/admin/*``).

Superficie de SOBERANÍA del operador. Todos los endpoints son **solo lectura** y
gateados con ``CurrentAdmin`` (``get_current_admin``): firma/exp/type/blocklist del JWT
+ flag ``is_admin`` o bootstrap (``ADMIN_BOOTSTRAP_IDS``). Sin admin -> 401 estático.

Privacidad (regla #4) — invariantes NO re-litigables:

(1) NUNCA se descifra contenido de memoria (``semantic_memory.content`` /
    ``episodic_memory.summary`` / ``conversation_turns.content``). Las métricas del moat
    son COUNT/GROUP BY puros + metadata no cifrada (``occurred_at``, ``is_sensitive``,
    ``confidence``, ``stale``).
(2) El audit del panel NUNCA expone ``record_hash`` (cadena de integridad) ni
    ``target_id`` (estructura interna del moat): el SELECT no los trae y el schema
    (``AdminAuditRow``) tampoco los declara.
(3) Las métricas son agregados globales (cross-user) para el operador del panel; los UUID
    que sí viajan (id de audit / episodic) son opacos, sin email ni PII.

Honestidad de dato (gaps del schema, ver recon): DAU/WAU/MAU son **aproximados** por
sesiones (no hay ``last_seen``); la conversión efímero->registrado es **estimada** (no
hay timestamp de conversión); la duración por modo solo cuenta sesiones cerradas.

Sin agregados precalculados: todo es COUNT/GROUP BY on-the-fly (patrón de ``sessions.py``:
``select(func.count()).select_from(...)`` + ``func.date_trunc`` para series). El audit
pagina con ``limit``/``offset``.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import Float, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.core.db_guard import _host_of, is_prod_db_host
from app.core.deps import CurrentAdmin, DbSession
from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode, enum_values
from app.models.audit import AuditLog
from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.admin import (
    ActivityMetric,
    AdminMoatOut,
    AdminModesOut,
    AdminOverviewOut,
    AdminSystemOut,
    AdminUsersOut,
    AuditPreviewRow,
    ConfidenceBucket,
    Consolidation,
    Conversion,
    Delta,
    HeatmapCell,
    KpiValueDelta,
    KpiValueDeltaSpark,
    LayerGrowth,
    MoatCounts,
    MoatDeltas,
    ModeCount,
    ModeDurationRow,
    ModeMixRow,
    OverviewKpis,
    Perimeter,
    ProceduralHealth,
    RecentEpisodic,
    ServiceStatus,
    SignupPoint,
    SystemGuard,
    SystemRuntime,
    SystemServices,
    TimePoint,
    UsersActivity,
)
from app.schemas.admin_api import AdminAuditPage, AdminAuditRow

router = APIRouter()

# Rango temporal soportado por el dashboard (default 7d). /system NO toma rango.
RangeId = Literal["24h", "7d", "30d", "90d"]
_RANGE_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}

RangeParam = Annotated[RangeId, Query()]

# Default + cap de la paginación del audit (igual que ``/v1/sessions`` / ``/v1/memory``).
_AUDIT_LIMIT_DEFAULT = 50
_AUDIT_LIMIT_MAX = 100

# Ventana del heatmap de actividad (estilo GitHub: 53 semanas).
_HEATMAP_DAYS = 53 * 7


# ---------------------------------------------------------------------------
# Helpers de cálculo (locales al router; single-use, sin abstracción prematura)
# ---------------------------------------------------------------------------


def _window(range_id: str) -> tuple[datetime, datetime, datetime]:
    """Devuelve ``(prev_start, start, now)`` para el rango pedido.

    ``[start, now)`` es el período actual; ``[prev_start, start)`` es el período anterior
    de igual longitud, usado para calcular deltas.
    """
    now = datetime.now(UTC)
    delta = _RANGE_DELTAS[range_id]
    start = now - delta
    prev_start = start - delta
    return prev_start, start, now


def _delta(current: int, previous: int) -> Delta:
    """Delta porcentual + dirección entre el período actual y el anterior.

    Sin período anterior (``previous == 0``): ``flat`` con ``pct`` 0 si el actual también
    es 0, o 100 si creció desde cero (evita división por cero, dato honesto).
    """
    if previous == 0:
        if current == 0:
            return Delta(pct=0.0, direction="flat")
        return Delta(pct=100.0, direction="up")
    pct = round((current - previous) / previous * 100, 1)
    direction: Literal["up", "down", "flat"] = (
        "up" if pct > 0 else "down" if pct < 0 else "flat"
    )
    return Delta(pct=pct, direction=direction)


async def _count(session: AsyncSession, stmt: object) -> int:
    """Ejecuta un ``select(func.count())...`` y devuelve el entero (0 si None)."""
    return (await session.scalar(stmt)) or 0  # type: ignore[arg-type]


async def _daily_series(
    session: AsyncSession,
    *,
    date_column: object,
    start: datetime,
    now: datetime,
    where: object | None = None,
) -> list[TimePoint]:
    """Serie diaria (COUNT por ``date_trunc('day', ...)``) rellenando días sin datos con 0."""
    bucket = func.date_trunc("day", date_column)
    stmt = select(bucket.label("day"), func.count().label("n"))
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.where(date_column >= start).group_by(bucket).order_by(bucket)
    rows = (await session.execute(stmt)).all()
    counts: dict[date, int] = {row.day.date(): int(row.n) for row in rows}
    points: list[TimePoint] = []
    cursor = start.date()
    end = now.date()
    while cursor <= end:
        points.append(TimePoint(date=cursor.isoformat(), value=counts.get(cursor, 0)))
        cursor += timedelta(days=1)
    return points


def _heat_level(count: int, peak: int) -> int:
    """Mapea un conteo a un nivel 0..5 relativo al pico de la ventana."""
    if count <= 0 or peak <= 0:
        return 0
    ratio = count / peak
    for level, threshold in ((5, 0.85), (4, 0.62), (3, 0.38), (2, 0.18), (1, 0.0)):
        if ratio > threshold:
            return level
    return 1


# ---------------------------------------------------------------------------
# 4.1 GET /v1/admin/overview
# ---------------------------------------------------------------------------


@router.get("/admin/overview", response_model=AdminOverviewOut, status_code=200)
async def admin_overview(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminOverviewOut:
    """KPIs + serie de sesiones + mix de modos + preview de audit, para el rango pedido."""
    prev_start, start, now = _window(range)

    # KPIs ------------------------------------------------------------------
    users_total = await _count(session, select(func.count()).select_from(User))
    users_prev = await _count(
        session, select(func.count()).select_from(User).where(User.created_at < start)
    )
    users_total_kpi = KpiValueDelta(
        value=users_total, delta=_delta(users_total, users_prev)
    )

    sessions_cur = await _count(
        session,
        select(func.count()).select_from(ChatSession).where(ChatSession.started_at >= start),
    )
    sessions_prev = await _count(
        session,
        select(func.count())
        .select_from(ChatSession)
        .where(ChatSession.started_at >= prev_start, ChatSession.started_at < start),
    )
    sessions_series = await _daily_series(
        session, date_column=ChatSession.started_at, start=start, now=now
    )
    sessions_kpi = KpiValueDeltaSpark(
        value=sessions_cur,
        delta=_delta(sessions_cur, sessions_prev),
        spark=[p.value for p in sessions_series],
    )

    memories_total = (
        await _count(session, select(func.count()).select_from(SemanticMemory))
        + await _count(session, select(func.count()).select_from(EpisodicMemory))
        + await _count(session, select(func.count()).select_from(ProceduralMemory))
    )
    mem_prev = (
        await _count(
            session,
            select(func.count())
            .select_from(SemanticMemory)
            .where(SemanticMemory.created_at < start),
        )
        + await _count(
            session,
            select(func.count())
            .select_from(EpisodicMemory)
            .where(EpisodicMemory.created_at < start),
        )
        + await _count(
            session,
            select(func.count())
            .select_from(ProceduralMemory)
            .where(ProceduralMemory.created_at < start),
        )
    )
    memories_kpi = KpiValueDelta(value=memories_total, delta=_delta(memories_total, mem_prev))

    audit_cur = await _count(
        session, select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= start)
    )
    audit_prev = await _count(
        session,
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.created_at >= prev_start, AuditLog.created_at < start),
    )
    audit_kpi = KpiValueDelta(value=audit_cur, delta=_delta(audit_cur, audit_prev))

    # Mix de modos (sesiones por modo en la ventana) -----------------------
    mix_rows = (
        await session.execute(
            select(ChatSession.mode, func.count())
            .where(ChatSession.started_at >= start)
            .group_by(ChatSession.mode)
        )
    ).all()
    mode_mix = [ModeCount(mode=row[0], value=int(row[1])) for row in mix_rows]

    # Preview de audit (últimas 6, sin record_hash / target_id) ------------
    preview_rows = (
        await session.execute(
            select(
                AuditLog.id,
                AuditLog.created_at,
                AuditLog.operation,
                AuditLog.target_layer,
                AuditLog.origin_mode,
                AuditLog.sensitive,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(6)
        )
    ).all()
    audit_preview = [
        AuditPreviewRow(
            id=row.id,
            created_at=row.created_at,
            operation=row.operation,
            target_layer=row.target_layer,
            origin_mode=row.origin_mode,
            sensitive=row.sensitive,
        )
        for row in preview_rows
    ]

    return AdminOverviewOut(
        perimeter=Perimeter(status="intact", detail=None, checked_at=now),
        kpis=OverviewKpis(
            users_total=users_total_kpi,
            sessions=sessions_kpi,
            memories=memories_kpi,
            audit_events=audit_kpi,
        ),
        sessions_series=sessions_series,
        mode_mix=mode_mix,
        audit_preview=audit_preview,
    )


# ---------------------------------------------------------------------------
# 4.2 GET /v1/admin/users
# ---------------------------------------------------------------------------


async def _active_users(
    session: AsyncSession, *, start: datetime, end: datetime | None = None
) -> int:
    """DISTINCT user_id con una sesión iniciada en ``[start, end)`` (proxy de actividad)."""
    stmt = (
        select(func.count(func.distinct(ChatSession.user_id)))
        .select_from(ChatSession)
        .where(ChatSession.started_at >= start)
    )
    if end is not None:
        stmt = stmt.where(ChatSession.started_at < end)
    return await _count(session, stmt)


async def _activity_metric(
    session: AsyncSession, *, window: timedelta, now: datetime
) -> ActivityMetric:
    """Construye un ActivityMetric (DAU/WAU/MAU) con delta vs período anterior + sparkline."""
    start = now - window
    prev_start = start - window
    current = await _active_users(session, start=start)
    previous = await _active_users(session, start=prev_start, end=start)
    # Sparkline: usuarios activos por día dentro de la ventana.
    spark_points = await _daily_series(
        session, date_column=ChatSession.started_at, start=start, now=now
    )
    return ActivityMetric(
        value=current,
        delta=_delta(current, previous),
        spark=[p.value for p in spark_points],
    )


@router.get("/admin/users", response_model=AdminUsersOut, status_code=200)
async def admin_users(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminUsersOut:
    """Actividad aprox. (DAU/WAU/MAU por sesiones), heatmap, conversión estimada, signups."""
    now = datetime.now(UTC)
    _, start, _ = _window(range)

    dau = await _activity_metric(session, window=timedelta(days=1), now=now)
    wau = await _activity_metric(session, window=timedelta(days=7), now=now)
    mau = await _activity_metric(session, window=timedelta(days=30), now=now)

    # Heatmap de actividad (sesiones/día, últimas 53 semanas) --------------
    heat_start = now - timedelta(days=_HEATMAP_DAYS)
    heat_points = await _daily_series(
        session, date_column=ChatSession.started_at, start=heat_start, now=now
    )
    peak = max((p.value for p in heat_points), default=0)
    heatmap = [
        HeatmapCell(date=p.date, count=p.value, level=_heat_level(p.value, peak))
        for p in heat_points
    ]

    # Conversión efímero -> registrado (estimada) --------------------------
    ephemeral = await _count(
        session, select(func.count()).select_from(User).where(User.is_ephemeral.is_(True))
    )
    registered = await _count(
        session, select(func.count()).select_from(User).where(User.is_ephemeral.is_(False))
    )
    total_users = ephemeral + registered
    conversion_pct = round(registered / total_users * 100, 1) if total_users else 0.0

    # Signups por día (users.created_at) en la ventana del rango -----------
    signup_points = await _daily_series(
        session, date_column=User.created_at, start=start, now=now
    )
    signups = [SignupPoint(date=p.date, count=p.value) for p in signup_points]

    return AdminUsersOut(
        activity=UsersActivity(dau=dau, wau=wau, mau=mau, is_approximate=True),
        heatmap=heatmap,
        conversion=Conversion(
            ephemeral=ephemeral,
            registered=registered,
            conversion_pct=conversion_pct,
            is_estimate=True,
        ),
        signups=signups,
    )


# ---------------------------------------------------------------------------
# 4.3 GET /v1/admin/modes
# ---------------------------------------------------------------------------


@router.get("/admin/modes", response_model=AdminModesOut, status_code=200)
async def admin_modes(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminModesOut:
    """Mix de sesiones por modo + duración media (solo cerradas) por modo, en la ventana."""
    _, start, _ = _window(range)

    mix_rows = (
        await session.execute(
            select(ChatSession.mode, func.count())
            .where(ChatSession.started_at >= start)
            .group_by(ChatSession.mode)
        )
    ).all()
    counts: dict[Mode, int] = {row[0]: int(row[1]) for row in mix_rows}
    total = sum(counts.values())
    mix = [
        ModeMixRow(
            mode=mode,
            sessions=counts[mode],
            pct=round(counts[mode] / total * 100, 1) if total else 0.0,
        )
        for mode in counts
    ]

    # Duración media por modo: AVG(ended_at - started_at) en segundos -> minutos,
    # solo sesiones cerradas; las abiertas se cuentan aparte. NUNCA descifra nada.
    closed_secs = func.avg(
        func.extract("epoch", ChatSession.ended_at - ChatSession.started_at)
    )
    duration_rows = (
        await session.execute(
            select(
                ChatSession.mode,
                closed_secs.label("avg_secs"),
                func.count().filter(ChatSession.ended_at.isnot(None)).label("closed"),
                func.count().filter(ChatSession.ended_at.is_(None)).label("open"),
            )
            .where(ChatSession.started_at >= start)
            .group_by(ChatSession.mode)
        )
    ).all()
    duration = [
        ModeDurationRow(
            mode=row.mode,
            avg_minutes=round(float(row.avg_secs) / 60, 1) if row.avg_secs is not None else 0.0,
            closed_sessions=int(row.closed),
            open_sessions=int(row.open),
        )
        for row in duration_rows
    ]

    return AdminModesOut(total=total, mix=mix, duration=duration)


# ---------------------------------------------------------------------------
# 4.4 GET /v1/admin/moat
# ---------------------------------------------------------------------------


@router.get("/admin/moat", response_model=AdminMoatOut, status_code=200)
async def admin_moat(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminMoatOut:
    """Conteos por capa + crecimiento + salud procedural + consolidación. CERO descifrado."""
    prev_start, start, now = _window(range)

    # Conteos actuales por capa --------------------------------------------
    semantic = await _count(session, select(func.count()).select_from(SemanticMemory))
    episodic = await _count(session, select(func.count()).select_from(EpisodicMemory))
    procedural = await _count(session, select(func.count()).select_from(ProceduralMemory))

    # Deltas: filas creadas en la ventana actual vs la anterior ------------
    async def _layer_delta(model: type, created_col: object) -> Delta:
        cur = await _count(
            session, select(func.count()).select_from(model).where(created_col >= start)
        )
        prev = await _count(
            session,
            select(func.count())
            .select_from(model)
            .where(created_col >= prev_start, created_col < start),
        )
        return _delta(cur, prev)

    deltas = MoatDeltas(
        semantic=await _layer_delta(SemanticMemory, SemanticMemory.created_at),
        episodic=await _layer_delta(EpisodicMemory, EpisodicMemory.created_at),
        procedural=await _layer_delta(ProceduralMemory, ProceduralMemory.created_at),
    )

    # Crecimiento diario por capa (serie en la ventana) --------------------
    growth = [
        LayerGrowth(
            key=MemoryLayer.SEMANTIC,
            points=await _daily_series(
                session, date_column=SemanticMemory.created_at, start=start, now=now
            ),
        ),
        LayerGrowth(
            key=MemoryLayer.EPISODIC,
            points=await _daily_series(
                session, date_column=EpisodicMemory.created_at, start=start, now=now
            ),
        ),
        LayerGrowth(
            key=MemoryLayer.PROCEDURAL,
            points=await _daily_series(
                session, date_column=ProceduralMemory.created_at, start=start, now=now
            ),
        ),
    ]

    # Salud procedural: stale vs sano + histograma de confidence -----------
    stale_count = await _count(
        session,
        select(func.count()).select_from(ProceduralMemory).where(ProceduralMemory.stale.is_(True)),
    )
    healthy_count = procedural - stale_count
    # Histograma de confidence en 5 buckets [0,0.2)...[0.8,1.0].
    bucket_expr = func.width_bucket(cast(ProceduralMemory.confidence, Float), 0.0, 1.0, 5)
    bucket_rows = (
        await session.execute(
            select(bucket_expr.label("b"), func.count()).group_by(bucket_expr).order_by(bucket_expr)
        )
    ).all()
    bucket_counts: dict[int, int] = {int(row.b): int(row[1]) for row in bucket_rows}
    bucket_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    confidence_buckets = [
        # width_bucket devuelve 1..5 para [0,1]; el bucket 6 (==1.0) se suma al último.
        ConfidenceBucket(
            range=label,
            count=bucket_counts.get(idx + 1, 0) + (bucket_counts.get(6, 0) if idx == 4 else 0),
        )
        for idx, label in enumerate(bucket_labels)
    ]

    # Consolidación: backlog (sesiones cerradas sin episodic) + episodios recientes.
    backlog = await _count(
        session,
        select(func.count())
        .select_from(ChatSession)
        .outerjoin(EpisodicMemory, EpisodicMemory.session_id == ChatSession.id)
        .where(ChatSession.ended_at.isnot(None), EpisodicMemory.id.is_(None)),
    )
    recent_rows = (
        await session.execute(
            select(EpisodicMemory.id, EpisodicMemory.occurred_at, EpisodicMemory.is_sensitive)
            .order_by(EpisodicMemory.occurred_at.desc())
            .limit(6)
        )
    ).all()
    recent_episodic = [
        RecentEpisodic(id=row.id, occurred_at=row.occurred_at, is_sensitive=row.is_sensitive)
        for row in recent_rows
    ]

    return AdminMoatOut(
        counts=MoatCounts(semantic=semantic, episodic=episodic, procedural=procedural),
        deltas=deltas,
        growth=growth,
        procedural=ProceduralHealth(
            stale_count=stale_count,
            healthy_count=healthy_count,
            confidence_buckets=confidence_buckets,
        ),
        consolidation=Consolidation(backlog=backlog, recent_episodic=recent_episodic),
    )


# ---------------------------------------------------------------------------
# 4.5 GET /v1/admin/audit
# ---------------------------------------------------------------------------


@router.get("/admin/audit", response_model=AdminAuditPage, status_code=200)
async def admin_audit(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
    operation: Annotated[AuditOperation | None, Query()] = None,
    target_layer: Annotated[MemoryLayer | None, Query()] = None,
    origin_mode: Annotated[Mode | None, Query()] = None,
    origin_model: Annotated[LlmModel | None, Query()] = None,
    sensitive: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_AUDIT_LIMIT_MAX)] = _AUDIT_LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminAuditPage:
    """Página de audit filtrable. NUNCA expone ``record_hash`` ni ``target_id``.

    El SELECT trae solo los campos exponibles; ``record_hash``/``target_id`` no entran ni
    en la query ni en el schema. Filtra por rango (``created_at``) + facets opcionales,
    ordena por ``created_at`` DESC, pagina con ``limit``/``offset``.
    """
    _, start, _ = _window(range)

    filters = [AuditLog.created_at >= start]
    if operation is not None:
        filters.append(AuditLog.operation == operation)
    if target_layer is not None:
        filters.append(AuditLog.target_layer == target_layer)
    if origin_mode is not None:
        filters.append(AuditLog.origin_mode == origin_mode)
    if origin_model is not None:
        filters.append(AuditLog.origin_model == origin_model)
    if sensitive is not None:
        filters.append(AuditLog.sensitive.is_(sensitive))

    total = await _count(
        session, select(func.count()).select_from(AuditLog).where(*filters)
    )
    sensitive_total = await _count(
        session,
        select(func.count()).select_from(AuditLog).where(*filters, AuditLog.sensitive.is_(True)),
    )
    sensitive_pct = round(sensitive_total / total * 100, 1) if total else 0.0

    rows = (
        await session.execute(
            select(
                AuditLog.id,
                AuditLog.created_at,
                AuditLog.operation,
                AuditLog.target_layer,
                AuditLog.origin_mode,
                AuditLog.origin_model,
                AuditLog.origin_tool,
                AuditLog.sensitive,
            )
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = [
        AdminAuditRow(
            id=row.id,
            created_at=row.created_at,
            operation=row.operation,
            target_layer=row.target_layer,
            origin_mode=row.origin_mode,
            origin_model=row.origin_model,
            origin_tool=row.origin_tool,
            sensitive=row.sensitive,
        )
        for row in rows
    ]

    return AdminAuditPage(items=items, total=total, sensitive_pct=sensitive_pct)


# ---------------------------------------------------------------------------
# 4.6 GET /v1/admin/system
# ---------------------------------------------------------------------------


async def _probe_postgres(session: AsyncSession) -> ServiceStatus:
    """``SELECT 1`` contra la DB de la sesión actual. Reporta solo el tipo de error."""
    started = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - started) * 1000, 2)
        return ServiceStatus(
            up=True, latency_ms=latency, detail="SELECT 1", checked_at=datetime.now(UTC)
        )
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 2)
        return ServiceStatus(
            up=False, latency_ms=latency, detail=type(exc).__name__, checked_at=datetime.now(UTC)
        )


async def _probe_redis(request: Request) -> ServiceStatus:
    """PING al cliente Redis singleton (``app.state.redis``). Solo el tipo de error."""
    started = time.perf_counter()
    try:
        client = request.app.state.redis
        await client.ping()
        latency = round((time.perf_counter() - started) * 1000, 2)
        return ServiceStatus(
            up=True, latency_ms=latency, detail="PING", checked_at=datetime.now(UTC)
        )
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 2)
        return ServiceStatus(
            up=False, latency_ms=latency, detail=type(exc).__name__, checked_at=datetime.now(UTC)
        )


def _schema_head() -> str:
    """Head de Alembic leído del directorio de migraciones (sin tocar la DB).

    Defensivo: si no se puede resolver (config ausente), devuelve "unknown" en vez de
    romper el endpoint de salud.
    """
    try:
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        ini = Path(__file__).resolve().parents[3] / "alembic.ini"
        cfg = Config(str(ini))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        return heads[0] if heads else "unknown"
    except Exception:
        return "unknown"


@router.get("/admin/system", response_model=AdminSystemOut, status_code=200)
async def admin_system(
    request: Request,
    session: DbSession,
    admin_id: CurrentAdmin,
) -> AdminSystemOut:
    """Salud de infra + guard anti-prod + inventario de runtime. Sin queries de negocio."""
    settings = get_settings()

    is_prod_in_dev = settings.environment != "production" and is_prod_db_host(settings.database_url)
    # ``db_target``: solo el host (NUNCA el connection string con credenciales, regla #2).
    guard = SystemGuard(
        active=settings.environment != "production",
        db_target=_host_of(settings.database_url) or "unknown",
        is_prod_in_dev=is_prod_in_dev,
    )

    postgres = await _probe_postgres(session)
    redis = await _probe_redis(request)

    models = sorted({m for endpoint in settings.llm_serving for m in endpoint.models})
    runtime = SystemRuntime(
        models=models,
        modes=enum_values(Mode),
        schema_head=_schema_head(),
        embedder=settings.embedding_model,
        reranker=settings.reranker_model,
        build_version=__version__,
    )

    return AdminSystemOut(
        guard=guard,
        services=SystemServices(postgres=postgres, redis=redis),
        runtime=runtime,
    )
