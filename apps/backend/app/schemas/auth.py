"""Schemas HTTP del modulo ``/v1/auth`` (register + login).

Contrato wire de auth: separado de los schemas de dominio de usuario
(``app/schemas/user.py``). Hereda ``YnaraBaseModel`` (strict=True,
extra=forbid). La respuesta de ``register`` es ``UserOut`` (reusa el schema de
usuario, que NUNCA expone ``password_hash``); ``token`` devuelve ``TokenOut``.

NO se reusa ``UserCreate`` como request de register a proposito: su ``password``
es opcional y ademas trae ``is_ephemeral`` / ``retention_sensitive_days`` /
``onboarding_completed``, lo que abriria un mass-assignment desde el wire. El
request de register es un schema acotado a (email, password, display_name).

Nota de strict mode + el body de FastAPI (mismo caso que ``ChatHttpRequest``):
    ``YnaraBaseModel`` hereda ``strict=True``. FastAPI parsea el body JSON a un
    ``dict`` y valida con ``model_validate(dict)``. Los campos de los requests
    de auth son ``str`` / ``EmailStr`` (sin coercion enum/UUID), asi que strict
    los acepta tal cual del wire. Aun asi se override-a ``strict=False`` en
    ``RegisterRequest`` / ``LoginRequest`` por consistencia con el resto de los
    requests wire y para no depender de ese detalle; las constraints
    (``min_length`` / ``max_length``) y ``extra='forbid'`` se mantienen.
    ``TokenOut`` (response) sigue strict.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, EmailStr, Field

from app.schemas.base import YnaraBaseModel


class RegisterRequest(YnaraBaseModel):
    """Payload de ``POST /v1/auth/register``.

    Acotado a propósito (no reusa ``UserCreate``): el wire no puede setear
    ``is_ephemeral`` / ``retention_sensitive_days`` / ``onboarding_completed``.
    """

    # Override del strict heredado SOLO para el request wire (consistencia con
    # ChatHttpRequest). Los campos son str/EmailStr, pero relajar strict evita
    # depender de ese detalle. Constraints + extra=forbid siguen.
    model_config = ConfigDict(
        strict=False,
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=40)


class LoginRequest(YnaraBaseModel):
    """Payload de ``POST /v1/auth/token``.

    ``password`` SIN ``min_length`` / ``max_length`` a propósito: un 422 por
    longitud seria un oráculo de formato (revelaria la politica de password al
    atacante). Login solo distingue 200 / 401; la validez del password se decide
    en el service, no en el schema.
    """

    model_config = ConfigDict(
        strict=False,
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )

    email: EmailStr
    password: str


class TokenOut(YnaraBaseModel):
    """Response de ``POST /v1/auth/token``: el access token JWT (Bearer)."""

    access_token: str
    # S105: "bearer" no es una credencial; es el tipo de token del RFC 6750.
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
