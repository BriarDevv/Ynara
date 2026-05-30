"""Helpers de seguridad: hashing de contraseñas, JWT, scopes.

TODO: implementar al cerrar el módulo de auth. Este archivo es un
esqueleto.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Genera un JWT firmado con el secret de la app.

    TODO: implementar con python-jose. Acá queda el shape esperado.
    """
    settings = get_settings()
    _now = datetime.now(timezone.utc)
    _exp = _now + timedelta(minutes=settings.jwt_expire_minutes)
    _payload = {"sub": subject, "iat": _now, "exp": _exp, **(extra_claims or {})}
    # TODO: jose.jwt.encode(_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    raise NotImplementedError("create_access_token TODO")


def verify_access_token(token: str) -> dict[str, Any]:
    """Verifica un JWT y devuelve el payload."""
    # TODO: jose.jwt.decode(...)
    raise NotImplementedError("verify_access_token TODO")


def hash_password(plain: str) -> str:
    """Hashea contraseña con bcrypt."""
    # TODO: passlib.context.CryptContext(schemes=["bcrypt"])
    raise NotImplementedError("hash_password TODO")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica contraseña en texto plano contra su hash."""
    # TODO
    raise NotImplementedError("verify_password TODO")
