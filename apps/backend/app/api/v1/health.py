"""Endpoints de health check: liveness + readiness.

- ``GET /v1/health`` — **liveness**: el proceso responde. Barato, sin tocar
  dependencias. Siempre 200 si la app está viva.
- ``GET /v1/health/ready`` — **readiness**: pinga DB y Redis. Devuelve 503 si
  alguna dependencia no responde (para que el orquestador no rutee tráfico).

Los errores reportan solo el **nombre de la clase** de la excepción, nunca el
mensaje: un ``str(exc)`` de asyncpg/redis puede incluir el connection string con
credenciales (regla #2 / #4).
"""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.core.config import get_settings
from app.core.deps import engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


class DependencyCheck(BaseModel):
    ok: bool
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: str  # "ready" | "degraded"
    version: str
    checks: dict[str, DependencyCheck]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: el proceso está vivo y responde. No toca dependencias."""
    return HealthResponse(status="ok", version=__version__)


async def check_database() -> DependencyCheck:
    """Pinga la DB con ``SELECT 1``. Reporta solo el tipo de error (no el DSN)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return DependencyCheck(ok=True)
    except Exception as exc:
        # readiness no debe propagar: reporta solo el tipo, nunca str(exc) (DSN).
        return DependencyCheck(ok=False, error=type(exc).__name__)


async def check_redis() -> DependencyCheck:
    """Pinga Redis con PING. Reporta solo el tipo de error (no el DSN)."""
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    try:
        await client.ping()
        return DependencyCheck(ok=True)
    except Exception as exc:
        # readiness no debe propagar: reporta solo el tipo, nunca str(exc) (DSN).
        return DependencyCheck(ok=False, error=type(exc).__name__)
    finally:
        await client.aclose()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    """Readiness: 200 si DB y Redis responden, 503 (degraded) si alguna falla."""
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
    }
    ready = all(check.ok for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "degraded",
        version=__version__,
        checks=checks,
    )
