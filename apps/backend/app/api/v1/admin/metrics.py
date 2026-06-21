"""Métricas del panel admin: 5 GET de negocio (read-only) + ``/admin/system``.

Capa FINA: los 5 endpoints de negocio (overview / users / modes / moat / audit) delegan
en ``AdminMetricsService`` (``app/services/admin_metrics.py``); este módulo solo declara
las rutas, valida los query params (rango, facets, paginación) y arma el service.

``GET /admin/system`` queda acá (no en el service): es salud OPERACIONAL —probes de
Postgres/Redis + guard anti-prod + inventario de runtime—, no una métrica de negocio, y
necesita ``app.state`` (Redis singleton) + el head de Alembic. Lee ``app.state``, no la DB
de negocio.

Gate: todos con ``CurrentAdmin`` (``get_current_admin``): sin admin -> 401 estático.
Privacidad (regla #4): el service NUNCA descifra contenido ni expone ``record_hash`` /
``target_id``; ver su docstring.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.core.db_guard import _host_of, is_prod_db_host
from app.core.deps import CurrentAdmin, DbSession
from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode, enum_values
from app.schemas.admin import (
    AdminMoatOut,
    AdminModesOut,
    AdminOverviewOut,
    AdminSystemOut,
    AdminUsersOut,
    ServiceStatus,
    SystemGuard,
    SystemRuntime,
    SystemServices,
)
from app.schemas.admin_api import AdminAuditPage
from app.services.admin_metrics import AdminMetricsService

router = APIRouter()

# Rango temporal soportado por el dashboard (default 7d). /system NO toma rango.
RangeId = Literal["24h", "7d", "30d", "90d"]
RangeParam = Annotated[RangeId, Query()]

# Default + cap de la paginación del audit (igual que ``/v1/sessions`` / ``/v1/memory``).
_AUDIT_LIMIT_DEFAULT = 50
_AUDIT_LIMIT_MAX = 100


@router.get("/admin/overview", response_model=AdminOverviewOut, status_code=200)
async def admin_overview(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminOverviewOut:
    """KPIs + serie de sesiones + mix de modos + preview de audit, para el rango pedido."""
    return await AdminMetricsService(session).overview(range)


@router.get("/admin/users", response_model=AdminUsersOut, status_code=200)
async def admin_users(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminUsersOut:
    """Actividad aprox. (DAU/WAU/MAU por sesiones), heatmap, conversión estimada, signups."""
    return await AdminMetricsService(session).users(range)


@router.get("/admin/modes", response_model=AdminModesOut, status_code=200)
async def admin_modes(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminModesOut:
    """Mix de sesiones por modo + duración media (solo cerradas) por modo, en la ventana."""
    return await AdminMetricsService(session).modes(range)


@router.get("/admin/moat", response_model=AdminMoatOut, status_code=200)
async def admin_moat(
    session: DbSession,
    admin_id: CurrentAdmin,
    range: RangeParam = "7d",
) -> AdminMoatOut:
    """Conteos por capa + crecimiento + salud procedural + consolidación. CERO descifrado."""
    return await AdminMetricsService(session).moat(range)


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
    """Página de audit filtrable. NUNCA expone ``record_hash`` ni ``target_id`` (ver service)."""
    return await AdminMetricsService(session).audit(
        range_id=range,
        operation=operation,
        target_layer=target_layer,
        origin_mode=origin_mode,
        origin_model=origin_model,
        sensitive=sensitive,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /v1/admin/system — salud de infra + guard + runtime (operacional, no métrica)
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

        # ``apps/backend/alembic.ini`` — desde app/api/v1/admin/metrics.py son 4 niveles
        # (admin -> v1 -> api -> app -> backend = parents[4]).
        ini = Path(__file__).resolve().parents[4] / "alembic.ini"
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
