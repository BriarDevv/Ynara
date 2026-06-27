"""Schemas Pydantic para el dominio de usuario.

Mirror del modelo SQLAlchemy ``app/models/user.py``. La fuente de verdad
del contrato request/response es esta capa; el frontend (Zod en
``packages/shared-schemas/``) replica a mano cuando hace falta.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

from app.core.timezones import validate_iana_tz
from app.schemas.base import YnaraBaseModel


class UserBase(YnaraBaseModel):
    """Campos compartidos entre create/update/out."""

    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=40)
    is_ephemeral: bool = False
    onboarding_completed: bool = False
    # Huso horario IANA del usuario. Default ``UTC`` (espeja ``users.time_zone``
    # server_default). La validación IANA real se aplica en ``UserUpdate`` (la vía de
    # mutación desde el wire); ``UserOut`` se construye desde el ORM (valor ya válido).
    time_zone: str = Field(default="UTC")
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
    time_zone: str | None = None
    retention_sensitive_days: int | None = Field(default=None, ge=30, le=365)

    @field_validator("time_zone")
    @classmethod
    def _check_time_zone_iana(cls, v: str | None) -> str | None:
        """Valida que ``time_zone`` (si viene) sea un identificador IANA real.

        Reusa ``validate_iana_tz`` (sede única, DRY con ``calendar.py``). Un valor
        inválido -> ``PydanticCustomError`` (que Pydantic convierte en 422) con ``type``
        estable y SIN ecoar el string inválido (regla #4). ``None`` (campo no enviado)
        pasa intacto: el PATCH es parcial.
        """
        if v is None:
            return v
        try:
            return validate_iana_tz(v)
        except ValueError:
            # ``from None`` (regla #4): el ctx del custom error solo lleva loc/type,
            # nunca el valor original.
            raise PydanticCustomError(
                "invalid_time_zone",
                "time_zone debe ser un identificador IANA válido.",
            ) from None


class UserOut(UserBase):
    """Respuesta — incluye ID y timestamps; nunca el hash de password."""

    id: UUID
    created_at: datetime
    updated_at: datetime
