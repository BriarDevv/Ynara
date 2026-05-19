"""Schemas Pydantic para el dominio de usuario.

Mirror del modelo SQLAlchemy ``app/models/user.py``. La fuente de verdad
del contrato request/response es esta capa; el frontend (Zod en
``packages/shared-schemas/``) replica a mano cuando hace falta.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.base import YnaraBaseModel


class UserBase(YnaraBaseModel):
    """Campos compartidos entre create/update/out."""

    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=40)
    is_ephemeral: bool = False
    onboarding_completed: bool = False
    retention_sensitive_days: int = Field(default=180, ge=30, le=365)


class UserCreate(UserBase):
    """Payload para crear un usuario. ``password`` solo si no es
    ephemeral; se hashea en el service antes de persistir.
    """

    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdate(YnaraBaseModel):
    """Update parcial; cualquier campo opcional puede mandarse."""

    display_name: str | None = Field(default=None, max_length=40)
    onboarding_completed: bool | None = None
    retention_sensitive_days: int | None = Field(default=None, ge=30, le=365)


class UserOut(UserBase):
    """Respuesta — incluye ID y timestamps; nunca el hash de password."""

    id: UUID
    created_at: datetime
    updated_at: datetime
