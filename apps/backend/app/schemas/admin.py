"""Schemas Pydantic de las métricas del panel admin (/v1/admin/*).

DTOs de salida de los 6 endpoints de dashboard. Heredan ``YnaraBaseModel`` (strict +
from_attributes + extra=forbid) y emiten **snake_case** (la convención del repo; el
front matchea por nombre, no por alias). NO reutilizan ``schemas/memory.py`` ni
``schemas/audit.py`` (sagrados).

Privacidad (regla #4): estos DTOs son **agregados** (COUNT/GROUP BY) + metadata opaca.
NUNCA exponen contenido de memoria descifrado, ``record_hash`` ni PII. El ``AdminAuditRow``
omite ``record_hash`` y ``target_id`` **del schema** (no solo del render): ver
``app/schemas/admin_api.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.enums import AuditOperation, MemoryLayer, Mode
from app.schemas.base import YnaraBaseModel

# Dirección de un delta entre el período actual y el anterior.
DeltaDirection = Literal["up", "down", "flat"]
# Estado del perímetro de soberanía mostrado en el badge del panel.
PerimeterStatus = Literal["intact", "attention", "verifying"]


class Delta(YnaraBaseModel):
    """Variación porcentual + dirección entre el período actual y el anterior."""

    pct: float
    direction: DeltaDirection


class TimePoint(YnaraBaseModel):
    """Un punto de una serie temporal (conteo por día)."""

    date: str
    value: int


# ---------------------------------------------------------------------------
# 4.1 GET /v1/admin/overview
# ---------------------------------------------------------------------------


class Perimeter(YnaraBaseModel):
    """Estado del perímetro de soberanía (badge del panel)."""

    status: PerimeterStatus
    detail: str | None
    checked_at: datetime


class KpiValueDelta(YnaraBaseModel):
    """Un KPI con su valor y delta."""

    value: int
    delta: Delta


class KpiValueDeltaSpark(YnaraBaseModel):
    """Un KPI con valor, delta y sparkline."""

    value: int
    delta: Delta
    spark: list[int]


class OverviewKpis(YnaraBaseModel):
    """Los 4 KPIs del overview."""

    users_total: KpiValueDelta
    sessions: KpiValueDeltaSpark
    memories: KpiValueDelta  # suma de las 3 capas
    audit_events: KpiValueDelta


class ModeCount(YnaraBaseModel):
    """Conteo de sesiones por modo (mix)."""

    mode: Mode
    value: int


class AuditPreviewRow(YnaraBaseModel):
    """Fila mini del preview de audit en el overview (sin record_hash / target_id)."""

    id: UUID
    created_at: datetime
    operation: AuditOperation
    target_layer: MemoryLayer
    origin_mode: Mode | None
    sensitive: bool


class AdminOverviewOut(YnaraBaseModel):
    """Respuesta de ``GET /v1/admin/overview``."""

    perimeter: Perimeter
    kpis: OverviewKpis
    sessions_series: list[TimePoint]
    mode_mix: list[ModeCount]
    audit_preview: list[AuditPreviewRow]


# ---------------------------------------------------------------------------
# 4.2 GET /v1/admin/users
# ---------------------------------------------------------------------------


class ActivityMetric(YnaraBaseModel):
    """DAU/WAU/MAU: valor + delta + sparkline."""

    value: int
    delta: Delta
    spark: list[int]


class UsersActivity(YnaraBaseModel):
    """Actividad aproximada por sesiones (gap #1: no hay last_seen)."""

    dau: ActivityMetric
    wau: ActivityMetric
    mau: ActivityMetric
    is_approximate: Literal[True]


class HeatmapCell(YnaraBaseModel):
    """Una celda del heatmap de actividad (GitHub-style)."""

    date: str
    count: int
    level: int


class Conversion(YnaraBaseModel):
    """Conversión efímero -> registrado (estimada: sin timestamp de conversión)."""

    ephemeral: int
    registered: int
    conversion_pct: float
    is_estimate: Literal[True]


class SignupPoint(YnaraBaseModel):
    """Conteo de signups por día (``users.created_at``)."""

    date: str
    count: int


class AdminUsersOut(YnaraBaseModel):
    """Respuesta de ``GET /v1/admin/users``."""

    activity: UsersActivity
    heatmap: list[HeatmapCell]
    conversion: Conversion
    signups: list[SignupPoint]


# ---------------------------------------------------------------------------
# 4.3 GET /v1/admin/modes
# ---------------------------------------------------------------------------


class ModeMixRow(YnaraBaseModel):
    """Mix de sesiones por modo: conteo + porcentaje."""

    mode: Mode
    sessions: int
    pct: float


class ModeDurationRow(YnaraBaseModel):
    """Duración media por modo (solo sesiones cerradas) + abiertas aparte."""

    mode: Mode
    avg_minutes: float
    closed_sessions: int
    open_sessions: int


class AdminModesOut(YnaraBaseModel):
    """Respuesta de ``GET /v1/admin/modes``."""

    total: int
    mix: list[ModeMixRow]
    duration: list[ModeDurationRow]


# ---------------------------------------------------------------------------
# 4.4 GET /v1/admin/moat
# ---------------------------------------------------------------------------


class MoatCounts(YnaraBaseModel):
    """Conteo por capa de memoria (NUNCA se descifra contenido)."""

    semantic: int
    episodic: int
    procedural: int


class MoatDeltas(YnaraBaseModel):
    """Delta por capa de memoria."""

    semantic: Delta
    episodic: Delta
    procedural: Delta


class LayerGrowth(YnaraBaseModel):
    """Serie de crecimiento de una capa de memoria."""

    key: MemoryLayer
    points: list[TimePoint]


class ConfidenceBucket(YnaraBaseModel):
    """Un bucket del histograma de ``confidence`` procedural."""

    range: str
    count: int


class ProceduralHealth(YnaraBaseModel):
    """Salud de la memoria procedural: stale vs sano + histograma de confidence."""

    stale_count: int
    healthy_count: int
    confidence_buckets: list[ConfidenceBucket]


class RecentEpisodic(YnaraBaseModel):
    """Metadata de un episodio reciente (sin ``summary`` descifrado)."""

    id: UUID
    occurred_at: datetime
    is_sensitive: bool


class Consolidation(YnaraBaseModel):
    """Estado de consolidación: backlog + episodios recientes (solo metadata)."""

    backlog: int
    recent_episodic: list[RecentEpisodic]


class AdminMoatOut(YnaraBaseModel):
    """Respuesta de ``GET /v1/admin/moat``."""

    counts: MoatCounts
    deltas: MoatDeltas
    growth: list[LayerGrowth]
    procedural: ProceduralHealth
    consolidation: Consolidation


# ---------------------------------------------------------------------------
# 4.6 GET /v1/admin/system
# ---------------------------------------------------------------------------


class SystemGuard(YnaraBaseModel):
    """Guard anti-prod-en-dev (db_guard)."""

    active: bool
    db_target: str
    is_prod_in_dev: bool


class ServiceStatus(YnaraBaseModel):
    """Estado de un servicio de infra (postgres / redis)."""

    up: bool
    latency_ms: float
    detail: str
    checked_at: datetime


class SystemServices(YnaraBaseModel):
    """Estado de los servicios de infra."""

    postgres: ServiceStatus
    redis: ServiceStatus


class SystemRuntime(YnaraBaseModel):
    """Inventario de runtime/config no sensible."""

    models: list[str]
    modes: list[str]
    schema_head: str
    embedder: str
    reranker: str
    build_version: str


class AdminSystemOut(YnaraBaseModel):
    """Respuesta de ``GET /v1/admin/system``."""

    guard: SystemGuard
    services: SystemServices
    runtime: SystemRuntime
