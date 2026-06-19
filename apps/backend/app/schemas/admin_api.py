"""Wrappers de respuesta de la API ``/v1/admin/audit`` (NO sagrados).

Envelope de paginación del audit del panel admin. ``AdminAuditRow`` es la vista
**soberana** de ``audit_log``: **omite ``record_hash`` y ``target_id`` del schema**
(no solo del render) — el SELECT del endpoint tampoco los trae. Así la cadena de
integridad y la estructura interna del moat nunca filtran al panel (regla #4).

Separación deliberada (igual que ``session_api.py`` / ``memory_api.py``): los DTOs de
métricas viven en ``app/schemas/admin.py`` y el envelope de paginación vive acá.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.schemas.base import YnaraBaseModel


class AdminAuditRow(YnaraBaseModel):
    """Fila exponible de ``audit_log`` (SIN ``record_hash``, SIN ``target_id``).

    Campos exponibles del audit log per-user: metadata de la operación + su modo/modelo
    de origen + ``sensitive``. NUNCA incluye ``record_hash`` (cadena de integridad) ni
    ``target_id`` (apunta a memoria interna): ambos están ausentes del schema a propósito.
    """

    id: UUID
    created_at: datetime
    operation: AuditOperation
    target_layer: MemoryLayer
    origin_mode: Mode | None
    origin_model: LlmModel | None
    origin_tool: str | None
    sensitive: bool


class AdminAuditPage(YnaraBaseModel):
    """Página de filas de audit: ``items`` paginados + ``total`` + ``sensitive_pct``.

    ``items`` es la página ``limit``/``offset`` (ordenada por ``created_at`` DESC);
    ``total`` es el conteo COMPLETO que matchea los filtros (no el largo de la página);
    ``sensitive_pct`` es el porcentaje de filas sensibles dentro del total filtrado.
    """

    items: list[AdminAuditRow]
    total: int
    sensitive_pct: float
