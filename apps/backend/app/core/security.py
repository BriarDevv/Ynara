"""Helpers de seguridad: hashing de contraseñas y JWT.

JWT firmado con el secret de la app (``settings.jwt_secret``, HS256 por
default). Las contraseñas se hashean con bcrypt directo (no passlib: 1.7.4 no
es compatible con bcrypt 4.x). El módulo de auth (rutas ``/v1/auth``,
``get_current_user``) se arma encima de estos helpers.

Tokens (issue #63): todo access/refresh token lleva ``jti`` (uuid4 único, para
poder blocklistearlo) y ``type`` (``"access"`` | ``"refresh"``, para que
``/refresh`` no acepte un access como refresh ni viceversa). El refresh usa el
MISMO secret/alg que el access (simplicidad MVP); el claim ``type`` ya separa
los dominios, así que un access NO sirve como refresh aunque la firma valide.

Ningún mensaje de error filtra datos del usuario (regla #4): ``verify_token``
levanta ``InvalidTokenError`` sin distinguir expirado-vs-firma-inválida-vs-type
incorrecto (no dar un oráculo); el detalle de ``PyJWT`` queda en la cadena de la
excepción (``__cause__``), NUNCA en el string del error ni en una respuesta.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import get_settings

__all__ = [
    "SID_CLAIM",
    "InvalidTokenError",
    "create_access_token",
    "create_refresh_token",
    "hash_password",
    "verify_access_token",
    "verify_password",
    "verify_token",
]

# Nombre del claim de "session/family id" (sid): agrupa el access + todos los
# refresh rotados de una misma sesion bajo una unica unidad de revocacion
# (item 1 de #142). No es un claim de control falsificable (su unico uso es
# agrupar tokens de una sesion bajo una key de revocacion que el server controla),
# asi que va legitimamente en `extra_claims`. Se comparte como constante entre
# auth.py y deps.py para evitar un typo silencioso que rompa la family-revocation.
SID_CLAIM = "sid"

# bcrypt solo usa los primeros 72 bytes de la contraseña y bcrypt >= 4.1 levanta
# si se pasan más (en vez de truncar). Truncamos explícito. Usamos bcrypt directo
# (no passlib): passlib 1.7.4 no es compatible con bcrypt 4.x.
_BCRYPT_MAX_BYTES = 72

TokenType = Literal["access", "refresh"]


def _to_bcrypt_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


class InvalidTokenError(Exception):
    """Token JWT inválido: firma mala, expirado, malformado o ``type`` incorrecto."""


def _build_token(
    *,
    subject: str,
    token_type: TokenType,
    expire_minutes: int,
    jti: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Arma + firma un JWT con sub/iat/exp/jti/type (y claims extra opcionales).

    Los claims de control (``sub``/``iat``/``exp``/``jti``/``type``) van DESPUÉS
    de ``extra_claims`` en el dict: así ``extra_claims`` NO puede override-ar el
    ``type``, el ``exp``, ni el ``jti`` (defensa anti-falsificación de claims).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        **(extra_claims or {}),
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
        "jti": jti,
        "type": token_type,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    *,
    jti: str | None = None,
) -> str:
    """Genera un access JWT firmado con sub/iat/exp/jti/type + claims extra.

    ``subject`` es el identificador del usuario (``user.id`` como string). La
    expiración sale de ``settings.jwt_expire_minutes``.

    ``jti`` (uuid4 hex si no se pasa) hace al token revocable: el logout/rotación
    lo blocklistea. Se devuelve el ``jti`` dentro del propio payload, así que el
    caller que necesite blocklistear puede decodificarlo. El default
    (``create_access_token(str(user.id))``) sigue funcionando sin cambios:
    backward-compat de la firma intacta.

    ``extra_claims`` NO puede override-ar ``type``/``exp``/``jti`` (van después en
    el payload). Todo access token emitido tiene ``type == "access"``.
    """
    settings = get_settings()
    return _build_token(
        subject=subject,
        # S106: "access" es el discriminante del claim `type`, no una credencial.
        token_type="access",  # noqa: S106
        expire_minutes=settings.jwt_expire_minutes,
        jti=jti or uuid4().hex,
        extra_claims=extra_claims,
    )


def create_refresh_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    *,
    jti: str | None = None,
) -> str:
    """Genera un refresh JWT firmado con sub/iat/exp/jti/type=="refresh" + claims extra.

    TTL desde ``settings.jwt_refresh_expire_minutes`` (mayor que el access).
    Usa el MISMO secret/alg que el access (simplicidad MVP): el claim ``type``
    ya separa los dominios, así que ``verify_token(..., expected_type="refresh")``
    rechaza un access aunque la firma valide, y viceversa.

    El ``jti`` (uuid4 hex si no se pasa) hace al refresh rotable: ``/refresh`` lo
    blocklistea al consumirlo (single-use), y un reuse del viejo cae en la
    detección de replay.

    ``extra_claims`` (espejo de ``create_access_token``) NO puede override-ar
    ``type``/``exp``/``jti`` (van DESPUÉS en el payload, ver ``_build_token``); lo
    usa el flujo de refresh para propagar el ``sid`` (familia, item 1 de #142). El
    default (``create_refresh_token(str(user.id))``) sigue funcionando sin cambios.
    """
    settings = get_settings()
    return _build_token(
        subject=subject,
        # S106: "refresh" es el discriminante del claim `type`, no una credencial.
        token_type="refresh",  # noqa: S106
        expire_minutes=settings.jwt_refresh_expire_minutes,
        jti=jti or uuid4().hex,
        extra_claims=extra_claims,
    )


def _decode_token(token: str) -> dict[str, Any]:
    """Decodifica + valida firma/exp. Levanta ``InvalidTokenError`` ante cualquier fallo.

    No distingue el motivo (firma/exp/malformado) hacia afuera: el string es
    estático (``"token inválido"``); el detalle de ``PyJWT`` queda solo en
    ``__cause__`` (regla #4: nunca en la respuesta ni en un log con ``str(exc)``).
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            # Defensa en profundidad: exigir `exp` presente (PyJWT por default NO
            # lo requiere) para que ningún token sin expiración sea válido. En
            # PyJWT el claim obligatorio va en `require: [...]` (no el `require_exp`
            # de python-jose, que PyJWT ignoraría en silencio). `jti` NO se exige
            # para no romper tokens viejos en vuelo minteados antes de #63 (sin jti).
            options={"require": ["exp"], "verify_exp": True},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("token inválido") from exc


def verify_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica + valida firma/exp y exige que el claim ``type`` coincida.

    Levanta ``InvalidTokenError`` si la firma/exp/malformado fallan, O si el
    ``type`` no coincide con ``expected_type``. El mismatch de ``type`` NO se
    distingue del resto de los fallos (mismo string estático, sin oráculo).

    Compat de tokens en vuelo (pre-#63): con ``expected_type="access"`` se acepta
    también la AUSENCIA de ``type`` (tokens viejos no lo tenían), para no
    invalidar toda la base de sesiones activas en el deploy. Con
    ``expected_type="refresh"`` se exige ``type == "refresh"`` estricto (no hay
    refresh tokens viejos en vuelo).
    """
    payload = _decode_token(token)
    actual = payload.get("type")
    if expected_type == "access":
        # AUSENCIA de type => access (compat de tokens pre-#63 en vuelo).
        if actual not in (None, "access"):
            raise InvalidTokenError("token inválido")
    elif actual != expected_type:  # refresh: estricto (no hay viejos en vuelo).
        raise InvalidTokenError("token inválido")
    return payload


def verify_access_token(token: str) -> dict[str, Any]:
    """Verifica un access JWT y devuelve el payload (backward-compat).

    Delega en ``verify_token(token, expected_type="access")``: levanta
    ``InvalidTokenError`` si la firma es inválida, el token expiró, está
    malformado o su ``type`` no es ``"access"`` (un refresh no autentica como
    access). Acepta tokens viejos sin ``type`` (compat de despliegue). El detalle
    de ``PyJWT`` queda en la cadena de la excepción para debug, NUNCA expuesto.
    """
    return verify_token(token, expected_type="access")


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
