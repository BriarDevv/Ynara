"""Endpoint de health check."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness + readiness chequeo.

    TODO: agregar checks reales (DB ping, Redis ping, vLLM ping) y
    devolver 503 si alguno falla. Para readiness en serio.
    """
    return HealthResponse(status="ok", version=__version__)
