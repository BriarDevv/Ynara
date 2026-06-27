"""Schemas Pydantic del dominio de device token (push).

``DeviceRegister`` es el body de ``POST /v1/devices`` (upsert por token);
``DeviceUnregister`` el de ``DELETE /v1/devices`` (el token va por BODY, no por path:
es una credencial y no debe viajar en la URL — regla #4). ``DeviceTokenOut`` es el
device del wire: NO expone ``user_id`` (mismo criterio que ``TaskOut`` /
``CalendarEventOut``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from app.enums import DevicePlatform
from app.schemas.base import YnaraBaseModel

# El ``token`` es un string no vacío y acotado (512, igual que la columna). Las request
# llegan como JSON: ``platform`` viaja como string (``"ios"``) y debe coercionarse a
# ``DevicePlatform``, así que los bodies override-an ``strict=False`` a nivel modelo
# (MISMO patrón que ``TaskCreate`` / ``EventCreate``) manteniendo constraints +
# ``extra='forbid'``. ``DeviceTokenOut`` (respuesta) hereda strict: se construye desde el
# ORM (tipos reales) o desde el dict JSON-safe del store con ``strict=False`` puntual.
_Token = Annotated[str, Field(min_length=1, max_length=512)]
_WIRE_REQUEST_CONFIG = ConfigDict(
    strict=False,
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)


class DeviceRegister(YnaraBaseModel):
    """Body de ``POST /v1/devices`` (registrar/upsert un device token)."""

    model_config = _WIRE_REQUEST_CONFIG

    platform: DevicePlatform
    token: _Token


class DeviceUnregister(YnaraBaseModel):
    """Body de ``DELETE /v1/devices`` (des-registrar por token).

    El token va por BODY (no por path): es una credencial de envío y no debe aparecer en
    URLs / logs de acceso (regla #4).
    """

    model_config = _WIRE_REQUEST_CONFIG

    token: _Token


class DeviceTokenOut(YnaraBaseModel):
    """El device token serializado para el wire.

    Mirror del modelo MENOS ``user_id`` / ``created_at`` / ``updated_at`` (no viajan).
    """

    id: UUID
    platform: DevicePlatform
    token: _Token
    last_seen_at: datetime
