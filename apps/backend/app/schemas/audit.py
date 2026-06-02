"""Schemas Pydantic para audit log de operaciones sobre memoria.

El endpoint de lectura del audit log está planificado para una ola futura;
aún no está implementado. La escritura es interna al backend — no se expone
payload de creación.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.schemas.base import YnaraBaseModel


class AuditLogOut(YnaraBaseModel):
    """Una entrada de audit. Inmutable post-creación."""

    id: UUID
    user_id: UUID
    operation: AuditOperation
    target_layer: MemoryLayer
    target_id: UUID | None
    origin_model: LlmModel | None
    origin_mode: Mode | None
    origin_tool: str | None
    record_hash: str
    sensitive: bool
    created_at: datetime
