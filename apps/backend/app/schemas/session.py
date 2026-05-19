"""Schemas Pydantic para el dominio de sesión de chat."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.enums import Mode
from app.schemas.base import YnaraBaseModel


class SessionCreate(YnaraBaseModel):
    """Payload para abrir una sesión. ``user_id`` viene del JWT (no del
    body)."""

    mode: Mode


class SessionClose(YnaraBaseModel):
    """Payload para cerrar una sesión. ``ended_at`` lo setea el server
    con ``now()``; este schema solo confirma la intención."""

    session_id: UUID


class SessionOut(YnaraBaseModel):
    """Respuesta — incluye timestamps y user_id."""

    id: UUID
    user_id: UUID
    mode: Mode
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
