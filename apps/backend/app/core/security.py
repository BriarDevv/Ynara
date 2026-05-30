"""Helpers de seguridad: hashing de contraseñas y JWT.

JWT firmado con el secret de la app (``settings.jwt_secret``, HS256 por
default). Las contraseñas se hashean con bcrypt directo (no passlib: 1.7.4 no
es compatible con bcrypt 4.x). El módulo de auth (rutas ``/v1/auth``,
``get_current_user``) se arma encima de estos helpers.

Ningún mensaje de error filtra datos del usuario (regla #4): ``verify_access_token``
levanta ``InvalidTokenError`` sin distinguir expirado-vs-firma-inválida (no dar
un oráculo al atacante); el detalle de ``jose`` queda en la cadena de la excepción.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

__all__ = [
    "InvalidTokenError",
    "create_access_token",
    "hash_password",
    "verify_access_token",
    "verify_password",
]

# bcrypt solo usa los primeros 72 bytes de la contraseña y bcrypt >= 4.1 levanta
# si se pasan más (en vez de truncar). Truncamos explícito. Usamos bcrypt directo
# (no passlib): passlib 1.7.4 no es compatible con bcrypt 4.x.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


class InvalidTokenError(Exception):
    """Token JWT inválido: firma mala, expirado o malformado."""


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Genera un JWT firmado con sub/iat/exp + claims extra.

    ``subject`` es el identificador del usuario (``user.id`` como string). La
    expiración sale de ``settings.jwt_expire_minutes``.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> dict[str, Any]:
    """Verifica un JWT y devuelve el payload.

    Levanta ``InvalidTokenError`` si la firma es inválida, el token expiró o
    está malformado. No se distingue el motivo hacia afuera (evita un oráculo);
    el detalle de ``jose`` queda en la cadena de la excepción para debug.
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            # Defensa en profundidad: exigir exp (jose no lo requiere por
            # default) para que ningún token sin expiración sea válido.
            # python-jose usa `require_exp`, no el `require: [...]` de PyJWT.
            options={"require_exp": True, "verify_exp": True},
        )
    except JWTError as exc:
        raise InvalidTokenError("token inválido") from exc


def hash_password(plain: str) -> str:
    """Hashea una contraseña con bcrypt (salt aleatorio por hash)."""
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash bcrypt.

    Devuelve ``False`` ante un hash malformado en vez de propagar: un hash
    corrupto en la DB no debe tumbar el login con una excepción.
    """
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("ascii"))
    except ValueError:
        return False
