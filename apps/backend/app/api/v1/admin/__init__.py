"""Panel admin interno (``/v1/admin/*``): subpaquete por superficie.

Superficie de SOBERANÍA del operador, gateada con ``CurrentAdmin``. El router del panel
se arma combinando 3 sub-routers, uno por superficie:

- ``metrics``      — 5 GET de métricas de negocio (overview/users/modes/moat/audit,
  delegan en ``AdminMetricsService``) + ``GET /admin/system`` (salud operacional).
- ``playground``   — inventario de serving + 3 probes de LLM aislados (ADR-018/019).
- ``connectivity`` — estado del tailnet + URLs para compartir el serving.

Wiring sin cambios: ``app/main.py`` sigue haciendo ``from app.api.v1 import admin`` +
``app.include_router(admin.router, prefix="/v1", tags=["admin"])``; ``admin.router`` es el
router combinado de abajo. Las rutas conservan sus paths exactos (``/admin/...``).

Privacidad (regla #4): cada superficie mantiene sus invariantes (ver los docstrings de
cada módulo): cero descifrado de contenido, nunca ``record_hash``/``target_id``/``base_url``,
errores sin ``str(exc)`` (solo ``type(exc).__name__``).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin import connectivity, metrics, playground

router = APIRouter()
router.include_router(metrics.router)
router.include_router(playground.router)
router.include_router(connectivity.router)
