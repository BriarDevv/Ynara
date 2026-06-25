"""Service de las métricas del panel admin: agregados read-only cross-user.

Capa de dominio entre los endpoints (``app/api/v1/admin/metrics.py``) y la DB para las
5 métricas de negocio del dashboard: overview / users / modes / moat / audit. Todo es
COUNT/GROUP BY/date_trunc on-the-fly (sin agregados precalculados), filtrado por rango.
NO importa FastAPI. La salud de infra (``/admin/system``: probes de Postgres/Redis +
runtime) NO vive acá: es operacional (lee ``app.state``), no una métrica de negocio.

Privacidad (regla #4) — invariantes NO re-litigables:

(1) NUNCA se descifra contenido de memoria (``semantic_memory.content`` /
    ``episodic_memory.summary`` / ``conversation_turns.content``). Las métricas son
    COUNT/GROUP BY puros + metadata no cifrada (``occurred_at``, ``is_sensitive``,
    ``confidence``, ``stale``).
(2) El audit NUNCA expone ``record_hash`` (cadena de integridad) ni ``target_id``
    (estructura interna del moat): el SELECT no los trae y el schema (``AdminAuditRow``)
    tampoco los declara.
(3) Las métricas son agregados globales (cross-user) para el operador; los UUID que sí
    viajan (id de audit / episodic) son opacos, sin email ni PII.

Honestidad de dato (gaps del schema): DAU/WAU/MAU son **aproximados** por sesiones (no
hay ``last_seen``); la conversión efímero->registrado es **estimada** (no hay timestamp
de conversión); la duración por modo solo cuenta sesiones cerradas.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Float, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog
from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.admin import (
    ActivityMetric,
    AdminMoatOut,
    AdminModesOut,
    AdminOverviewOut,
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
    SignupPoint,
    TimePoint,
    UsersActivity,
)
from app.schemas.admin_api import AdminAuditPage, AdminAuditRow

# Rango temporal soportado por el dashboard (default 7d). /system NO toma rango.
_RANGE_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}

# Ventana del heatmap de actividad (estilo GitHub: 53 semanas).
_HEATMAP_DAYS = 53 * 7


# ---------------------------------------------------------------------------
# Helpers puros (sin DB)
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
    direction: Literal["up", "down", "flat"] = "up" if pct > 0 else "down" if pct < 0 else "flat"
    return Delta(pct=pct, direction=direction)


def _heat_level(count: int, peak: int) -> int:
    """Mapea un conteo a un nivel 0..5 relativo al pico de la ventana."""
    if count <= 0 or peak <= 0:
        return 0
    ratio = count / peak
    for level, threshold in ((5, 0.85), (4, 0.62), (3, 0.38), (2, 0.18), (1, 0.0)):
        if ratio > threshold:
            return level
    return 1


class AdminMetricsService:
    """Calcula las 5 métricas de negocio del panel admin (read-only, cross-user).

    Una instancia por request, ligada a la sesión async. Todos los métodos son
    SELECT puros (COUNT/GROUP BY/date_trunc): no mutan, no commitean, no descifran.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Helpers con DB ------------------------------------------------------

    async def _count(self, stmt: Select[tuple[int]]) -> int:
        """Ejecuta un ``select(func.count())...`` y devuelve el entero (0 si None)."""
        return (await self._session.scalar(stmt)) or 0

    async def _daily_series(
        self,
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
        rows = (await self._session.execute(stmt)).all()
        counts: dict[date, int] = {row.day.date(): int(row.n) for row in rows}
        points: list[TimePoint] = []
        cursor = start.date()
        end = now.date()
        while cursor <= end:
            points.append(TimePoint(date=cursor.isoformat(), value=counts.get(cursor, 0)))
            cursor += timedelta(days=1)
        return points

    async def _active_users(self, *, start: datetime, end: datetime | None = None) -> int:
        """DISTINCT user_id con una sesión iniciada en ``[start, end)`` (proxy de actividad)."""
        stmt = (
            select(func.count(func.distinct(ChatSession.user_id)))
            .select_from(ChatSession)
            .where(ChatSession.started_at >= start)
        )
        if end is not None:
            stmt = stmt.where(ChatSession.started_at < end)
        return await self._count(stmt)

    async def _activity_metric(self, *, window: timedelta, now: datetime) -> ActivityMetric:
        """Construye un ActivityMetric (DAU/WAU/MAU) con delta vs período anterior + sparkline."""
        start = now - window
        prev_start = start - window
        current = await self._active_users(start=start)
        previous = await self._active_users(start=prev_start, end=start)
        # Sparkline: usuarios activos por día dentro de la ventana.
        spark_points = await self._daily_series(
            date_column=ChatSession.started_at, start=start, now=now
        )
        return ActivityMetric(
            value=current,
            delta=_delta(current, previous),
            spark=[p.value for p in spark_points],
        )

    async def _window_counts(
        self, model: object, col: object, *, start: datetime, prev_start: datetime
    ) -> tuple[int, int, int]:
        """``(total, cur, prev)`` en UNA query con ``COUNT(*) FILTER`` (SCAL-04).

        ``total`` = todas las filas; ``cur`` = ``col >= start`` (período actual); ``prev``
        = ``prev_start <= col < start`` (la ventana anterior de igual longitud, para el
        delta). Reemplaza los 3 ``COUNT`` seriales (total + cur + prev) por un solo
        round-trip — el panel admin no suma latencia de N queries por métrica.
        """
        row = (
            await self._session.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(col >= start).label("cur"),
                    func.count().filter(col >= prev_start, col < start).label("prev"),
                ).select_from(model)
            )
        ).one()
        return int(row.total), int(row.cur), int(row.prev)

    async def _cumulative_counts(
        self, model: object, col: object, *, start: datetime
    ) -> tuple[int, int]:
        """``(total, antes_de_start)`` en UNA query con ``COUNT(*) FILTER`` (SCAL-04).

        Para KPIs ACUMULATIVOS (users / memorias): el valor es el total y el delta compara
        contra cuántas filas existían ANTES del período (``col < start``), no contra la
        ventana anterior. Colapsa las 2 queries (total + prev) en una.
        """
        row = (
            await self._session.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(col < start).label("before"),
                ).select_from(model)
            )
        ).one()
        return int(row.total), int(row.before)

    # --- Métricas ------------------------------------------------------------

    async def overview(self, range_id: str) -> AdminOverviewOut:
        """KPIs + serie de sesiones + mix de modos + preview de audit, para el rango pedido."""
        prev_start, start, now = _window(range_id)

        # KPIs (SCAL-04: cada KPI colapsa sus COUNT total/cur/prev en UNA query con
        # COUNT(*) FILTER, en vez de 2-3 queries seriales por KPI) ----------
        users_total, users_before = await self._cumulative_counts(
            User, User.created_at, start=start
        )
        users_total_kpi = KpiValueDelta(value=users_total, delta=_delta(users_total, users_before))

        _, sessions_cur, sessions_prev = await self._window_counts(
            ChatSession, ChatSession.started_at, start=start, prev_start=prev_start
        )
        sessions_series = await self._daily_series(
            date_column=ChatSession.started_at, start=start, now=now
        )
        sessions_kpi = KpiValueDeltaSpark(
            value=sessions_cur,
            delta=_delta(sessions_cur, sessions_prev),
            spark=[p.value for p in sessions_series],
        )

        # Memorias: total + "antes de start" por capa (1 query c/u, antes 2), sumadas.
        sem_total, sem_before = await self._cumulative_counts(
            SemanticMemory, SemanticMemory.created_at, start=start
        )
        epi_total, epi_before = await self._cumulative_counts(
            EpisodicMemory, EpisodicMemory.created_at, start=start
        )
        proc_total, proc_before = await self._cumulative_counts(
            ProceduralMemory, ProceduralMemory.created_at, start=start
        )
        memories_total = sem_total + epi_total + proc_total
        mem_prev = sem_before + epi_before + proc_before
        memories_kpi = KpiValueDelta(value=memories_total, delta=_delta(memories_total, mem_prev))

        _, audit_cur, audit_prev = await self._window_counts(
            AuditLog, AuditLog.created_at, start=start, prev_start=prev_start
        )
        audit_kpi = KpiValueDelta(value=audit_cur, delta=_delta(audit_cur, audit_prev))

        # Mix de modos (sesiones por modo en la ventana) -------------------
        mix_rows = (
            await self._session.execute(
                select(ChatSession.mode, func.count())
                .where(ChatSession.started_at >= start)
                .group_by(ChatSession.mode)
            )
        ).all()
        mode_mix = [ModeCount(mode=row[0], value=int(row[1])) for row in mix_rows]

        # Preview de audit (últimas 6, sin record_hash / target_id) --------
        preview_rows = (
            await self._session.execute(
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

    async def users(self, range_id: str) -> AdminUsersOut:
        """Actividad aprox. (DAU/WAU/MAU por sesiones), heatmap, conversión estimada, signups."""
        now = datetime.now(UTC)
        _, start, _ = _window(range_id)

        dau = await self._activity_metric(window=timedelta(days=1), now=now)
        wau = await self._activity_metric(window=timedelta(days=7), now=now)
        mau = await self._activity_metric(window=timedelta(days=30), now=now)

        # Heatmap de actividad (sesiones/día, últimas 53 semanas) ----------
        heat_start = now - timedelta(days=_HEATMAP_DAYS)
        heat_points = await self._daily_series(
            date_column=ChatSession.started_at, start=heat_start, now=now
        )
        peak = max((p.value for p in heat_points), default=0)
        heatmap = [
            HeatmapCell(date=p.date, count=p.value, level=_heat_level(p.value, peak))
            for p in heat_points
        ]

        # Conversión efímero -> registrado (estimada) ----------------------
        ephemeral = await self._count(
            select(func.count()).select_from(User).where(User.is_ephemeral.is_(True))
        )
        registered = await self._count(
            select(func.count()).select_from(User).where(User.is_ephemeral.is_(False))
        )
        total_users = ephemeral + registered
        conversion_pct = round(registered / total_users * 100, 1) if total_users else 0.0

        # Signups por día (users.created_at) en la ventana del rango -------
        signup_points = await self._daily_series(date_column=User.created_at, start=start, now=now)
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

    async def modes(self, range_id: str) -> AdminModesOut:
        """Mix de sesiones por modo + duración media (solo cerradas) por modo, en la ventana."""
        _, start, _ = _window(range_id)

        mix_rows = (
            await self._session.execute(
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
        closed_secs = func.avg(func.extract("epoch", ChatSession.ended_at - ChatSession.started_at))
        duration_rows = (
            await self._session.execute(
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

    async def moat(self, range_id: str) -> AdminMoatOut:
        """Conteos por capa + crecimiento + salud procedural + consolidación. CERO descifrado."""
        prev_start, start, now = _window(range_id)

        # Conteo (total) + delta (cur vs prev) por capa, cada uno en UNA query con
        # COUNT(*) FILTER (SCAL-04): antes eran 3 counts + 3x2 de los deltas = 9 queries
        # seriales; ahora 3.
        semantic, sem_cur, sem_prev = await self._window_counts(
            SemanticMemory, SemanticMemory.created_at, start=start, prev_start=prev_start
        )
        episodic, epi_cur, epi_prev = await self._window_counts(
            EpisodicMemory, EpisodicMemory.created_at, start=start, prev_start=prev_start
        )
        procedural, proc_cur, proc_prev = await self._window_counts(
            ProceduralMemory, ProceduralMemory.created_at, start=start, prev_start=prev_start
        )
        deltas = MoatDeltas(
            semantic=_delta(sem_cur, sem_prev),
            episodic=_delta(epi_cur, epi_prev),
            procedural=_delta(proc_cur, proc_prev),
        )

        # Crecimiento diario por capa (serie en la ventana) ----------------
        growth = [
            LayerGrowth(
                key=MemoryLayer.SEMANTIC,
                points=await self._daily_series(
                    date_column=SemanticMemory.created_at, start=start, now=now
                ),
            ),
            LayerGrowth(
                key=MemoryLayer.EPISODIC,
                points=await self._daily_series(
                    date_column=EpisodicMemory.created_at, start=start, now=now
                ),
            ),
            LayerGrowth(
                key=MemoryLayer.PROCEDURAL,
                points=await self._daily_series(
                    date_column=ProceduralMemory.created_at, start=start, now=now
                ),
            ),
        ]

        # Salud procedural: stale vs sano + histograma de confidence -------
        stale_count = await self._count(
            select(func.count())
            .select_from(ProceduralMemory)
            .where(ProceduralMemory.stale.is_(True)),
        )
        healthy_count = procedural - stale_count
        # Histograma de confidence en 5 buckets [0,0.2)...[0.8,1.0].
        bucket_expr = func.width_bucket(cast(ProceduralMemory.confidence, Float), 0.0, 1.0, 5)
        bucket_rows = (
            await self._session.execute(
                select(bucket_expr.label("b"), func.count())
                .group_by(bucket_expr)
                .order_by(bucket_expr)
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
        backlog = await self._count(
            select(func.count())
            .select_from(ChatSession)
            .outerjoin(EpisodicMemory, EpisodicMemory.session_id == ChatSession.id)
            .where(ChatSession.ended_at.isnot(None), EpisodicMemory.id.is_(None)),
        )
        recent_rows = (
            await self._session.execute(
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

    async def audit(
        self,
        *,
        range_id: str,
        operation: AuditOperation | None,
        target_layer: MemoryLayer | None,
        origin_mode: Mode | None,
        origin_model: LlmModel | None,
        sensitive: bool | None,
        limit: int,
        offset: int,
    ) -> AdminAuditPage:
        """Página de audit filtrable. NUNCA expone ``record_hash`` ni ``target_id``.

        El SELECT trae solo los campos exponibles; ``record_hash``/``target_id`` no entran
        ni en la query ni en el schema. Filtra por rango (``created_at``) + facets
        opcionales, ordena por ``created_at`` DESC, pagina con ``limit``/``offset``.
        """
        _, start, _ = _window(range_id)

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

        total = await self._count(select(func.count()).select_from(AuditLog).where(*filters))
        sensitive_total = await self._count(
            select(func.count())
            .select_from(AuditLog)
            .where(*filters, AuditLog.sensitive.is_(True)),
        )
        sensitive_pct = round(sensitive_total / total * 100, 1) if total else 0.0

        rows = (
            await self._session.execute(
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
