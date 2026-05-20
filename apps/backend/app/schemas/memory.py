"""Schemas Pydantic para las 3 capas de memoria.

Tablas sagradas (regla #3). Para el cliente, ``content`` y ``summary``
se devuelven en **plaintext** (descifrados en el wrapper con
``app/core/crypto.py``); en la DB viven cifrados en BYTEA. Para el
embedding no hay schema público — es interno al motor de búsqueda.

Mirror del modelo SQLAlchemy ``app/models/memory.py``. Ver ADR-007.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import YnaraBaseModel


# ---------- Semantic ----------


class SemanticMemoryCreate(YnaraBaseModel):
    """Payload para escribir un hecho semántico. El wrapper cifra
    ``content`` antes de persistir."""

    content: str = Field(min_length=1, max_length=4096)
    importance: int | None = Field(default=None, ge=0, le=100)
    source_session_id: UUID | None = None


class SemanticMemoryUpdate(YnaraBaseModel):
    """Update parcial."""

    content: str | None = Field(default=None, min_length=1, max_length=4096)
    importance: int | None = Field(default=None, ge=0, le=100)


class SemanticMemoryOut(YnaraBaseModel):
    """Respuesta con ``content`` descifrado. El embedding no se expone.

    PRECONDICIÓN DEL WRAPPER: el wrapper de memoria
    (``app/memory/semantic.py``) debe pasar ``content`` ya descifrado
    como ``str``. ``YnaraBaseModel.strict=True`` rechaza ``bytes``
    casteado a ``str`` con ``ValidationError`` (defensa en
    profundidad), pero el wrapper es responsable de no construir
    este schema con el BYTEA crudo de la tabla.
    """

    id: UUID
    user_id: UUID
    content: str
    importance: int | None
    source_session_id: UUID | None
    created_at: datetime
    updated_at: datetime


# ---------- Episodic ----------


class EpisodicMemoryCreate(YnaraBaseModel):
    """Payload generado por el worker de Celery al cerrar una sesión.
    ``is_sensitive`` se infiere del modo de la sesión (true para
    Bienestar).

    Validación cross-field: si ``is_sensitive=True``, ``retention_days``
    queda capeado a 365 (ver ADR-007 D2 — máximo 12 meses para
    entradas sensibles). Espejo de la CHECK constraint
    ``retention_days_sensitive_cap`` en ``app/models/memory.py``.
    """

    session_id: UUID
    summary: str = Field(min_length=1, max_length=8192)
    occurred_at: datetime
    is_sensitive: bool = False
    retention_days: int = Field(default=365, ge=1, le=3650)
    topics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cap_sensitive_retention(self) -> "EpisodicMemoryCreate":
        if self.is_sensitive and self.retention_days > 365:
            raise ValueError(
                "retention_days no puede exceder 365 cuando is_sensitive=True "
                "(ADR-007 D2)"
            )
        return self


class EpisodicMemoryOut(YnaraBaseModel):
    """Respuesta con ``summary`` descifrado.

    PRECONDICIÓN DEL WRAPPER: el wrapper de memoria
    (``app/memory/episodic.py``) debe pasar ``summary`` ya descifrado
    como ``str``. ``YnaraBaseModel.strict=True`` rechaza ``bytes``
    casteado a ``str`` con ``ValidationError`` (defensa en
    profundidad), pero el wrapper es responsable de no construir
    este schema con el BYTEA crudo de la tabla.
    """

    id: UUID
    user_id: UUID
    session_id: UUID
    summary: str
    is_sensitive: bool
    retention_days: int
    occurred_at: datetime
    topics: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------- Procedural ----------


class ProceduralMemoryUpsert(YnaraBaseModel):
    """Payload para upsert por ``key``. Resetea ``confidence=1.0`` y
    ``last_reinforced_at=now()`` si el key ya existía."""

    key: str = Field(min_length=1, max_length=120)
    value: dict[str, Any]


class ProceduralMemoryOut(YnaraBaseModel):
    """Respuesta con todos los campos derivados del decay."""

    id: UUID
    user_id: UUID
    key: str
    value: dict[str, Any]
    confidence: float
    last_reinforced_at: datetime
    stale: bool
    created_at: datetime
    updated_at: datetime


# ---------- Settings ----------


class MemorySettingsUpdate(YnaraBaseModel):
    """Payload del endpoint ``PATCH /v1/memory/settings`` (ver ADR-007 D2)."""

    retention_sensitive_days: int | None = Field(default=None, ge=30, le=365)
