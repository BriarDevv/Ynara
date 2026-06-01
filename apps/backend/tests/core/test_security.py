"""Tests de los helpers de seguridad: JWT (create/verify) + hashing bcrypt.

Sin DB ni red. ``create_access_token`` / ``verify_access_token`` leen
``get_settings()`` internamente; en vez de tocar env global, parcheamos
``app.core.security.get_settings`` con un ``Settings`` determinista (secret
conocido) via la fixture ``patched_settings``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
    verify_token,
)

_SECRET = "test-secret-no-usar-en-prod"
_ALG = "HS256"


def _settings(*, expire_minutes: int = 60, refresh_expire_minutes: int = 43200) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET=_SECRET,
        JWT_ALGORITHM=_ALG,
        JWT_EXPIRE_MINUTES=expire_minutes,
        JWT_REFRESH_EXPIRE_MINUTES=refresh_expire_minutes,
    )


@pytest.fixture
def patched_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = _settings()
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    return settings


# ---------- JWT ----------


def test_token_round_trip(patched_settings: Settings) -> None:
    token = create_access_token("user-123")
    payload = verify_access_token(token)
    assert payload["sub"] == "user-123"
    assert "iat" in payload
    assert "exp" in payload


def test_token_carries_extra_claims(patched_settings: Settings) -> None:
    token = create_access_token("user-123", {"role": "admin"})
    payload = verify_access_token(token)
    assert payload["role"] == "admin"


def test_tampered_token_rejected(patched_settings: Settings) -> None:
    token = create_access_token("user-123")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(InvalidTokenError):
        verify_access_token(tampered)


def test_wrong_secret_rejected(patched_settings: Settings) -> None:
    # Firmado con OTRO secret -> la verificacion con el secret de la app falla.
    foreign = jwt.encode({"sub": "x"}, "otro-secret", algorithm=_ALG)
    with pytest.raises(InvalidTokenError):
        verify_access_token(foreign)


def test_expired_token_rejected(patched_settings: Settings) -> None:
    expired = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) - timedelta(hours=1)},
        _SECRET,
        algorithm=_ALG,
    )
    with pytest.raises(InvalidTokenError):
        verify_access_token(expired)


def test_garbage_token_rejected(patched_settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        verify_access_token("no-es-un-jwt")


def test_token_without_exp_rejected(patched_settings: Settings) -> None:
    # Defensa en profundidad: verify exige exp aunque jose no lo requiera.
    no_exp = jwt.encode({"sub": "x"}, _SECRET, algorithm=_ALG)
    with pytest.raises(InvalidTokenError):
        verify_access_token(no_exp)


# ---------- jti + type + refresh (issue #63) ----------


def test_access_token_has_jti_and_type(patched_settings: Settings) -> None:
    """Todo access token nace con jti (uuid hex) + type=='access' + sub."""
    token = create_access_token("user-123")
    payload = verify_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert isinstance(payload["jti"], str) and payload["jti"]


def test_access_token_explicit_jti_is_kept(patched_settings: Settings) -> None:
    """create_access_token(jti=...) fija el jti (logout/rotación lo necesitan)."""
    token = create_access_token("user-123", jti="fijo-123")
    payload = verify_access_token(token)
    assert payload["jti"] == "fijo-123"


def test_extra_claims_cannot_override_type_exp_jti(patched_settings: Settings) -> None:
    """extra_claims NO puede falsificar type/exp/jti (van DESPUÉS en el payload)."""
    token = create_access_token(
        "user-123",
        {"type": "refresh", "jti": "falsificado", "role": "admin"},
    )
    payload = verify_access_token(token)
    # type/jti se imponen sobre el intento de override; el claim "legítimo" sí entra.
    assert payload["type"] == "access"
    assert payload["jti"] != "falsificado"
    assert payload["role"] == "admin"


def test_refresh_token_type_and_longer_exp(patched_settings: Settings) -> None:
    """create_refresh_token => type=='refresh', jti presente, exp > access."""
    access = verify_access_token(create_access_token("user-123"))
    refresh = verify_token(create_refresh_token("user-123"), expected_type="refresh")
    assert refresh["type"] == "refresh"
    assert isinstance(refresh["jti"], str) and refresh["jti"]
    # El refresh expira más tarde que el access (43200 vs 60 minutos).
    assert refresh["exp"] > access["exp"]


def test_verify_token_rejects_refresh_as_access(patched_settings: Settings) -> None:
    """Un refresh NO autentica como access (type mismatch -> InvalidTokenError)."""
    refresh = create_refresh_token("user-123")
    with pytest.raises(InvalidTokenError):
        verify_token(refresh, expected_type="access")


def test_verify_token_rejects_access_as_refresh(patched_settings: Settings) -> None:
    """Un access NO sirve como refresh (type mismatch estricto -> InvalidTokenError)."""
    access = create_access_token("user-123")
    with pytest.raises(InvalidTokenError):
        verify_token(access, expected_type="refresh")


def test_legacy_token_without_type_accepted_as_access(patched_settings: Settings) -> None:
    """Token viejo sin claim 'type' (pre-#63) sigue validando como access (compat)."""
    from datetime import UTC, datetime, timedelta

    legacy = jwt.encode(
        {"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1)},
        _SECRET,
        algorithm=_ALG,
    )
    # No levanta: la ausencia de type se trata como access.
    payload = verify_access_token(legacy)
    assert payload["sub"] == "user-123"


def test_invalid_token_message_does_not_leak_cause(patched_settings: Settings) -> None:
    """El str de InvalidTokenError es estático ('token inválido'); no filtra jose (regla #4)."""
    with pytest.raises(InvalidTokenError) as exc_info:
        verify_access_token("no-es-un-jwt")
    assert str(exc_info.value) == "token inválido"
    # El detalle de jose queda solo en __cause__, nunca en el mensaje expuesto.
    assert "no-es-un-jwt" not in str(exc_info.value)


# ---------- password hashing ----------


def test_password_hash_and_verify() -> None:
    hashed = hash_password("clave-segura")
    assert hashed != "clave-segura"  # no es plaintext
    assert verify_password("clave-segura", hashed) is True
    assert verify_password("clave-mala", hashed) is False


def test_hash_is_salted() -> None:
    # bcrypt usa salt aleatorio: dos hashes de la misma clave difieren.
    assert hash_password("misma-clave") != hash_password("misma-clave")


def test_verify_password_malformed_hash_returns_false() -> None:
    assert verify_password("clave", "no-es-un-hash-bcrypt") is False
