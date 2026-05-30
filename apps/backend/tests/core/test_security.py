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
    hash_password,
    verify_access_token,
    verify_password,
)

_SECRET = "test-secret-no-usar-en-prod"
_ALG = "HS256"


def _settings(*, expire_minutes: int = 60) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET=_SECRET,
        JWT_ALGORITHM=_ALG,
        JWT_EXPIRE_MINUTES=expire_minutes,
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
