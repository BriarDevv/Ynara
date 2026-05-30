"""Tests del helper de cifrado de memoria (app/core/crypto.py, ADR-007 D3).

Sin DB ni red. ``encrypt_for_user`` / ``decrypt_for_user`` leen el master key de
``get_settings()``; lo parcheamos con un ``Settings`` determinista (key conocida
de 32 bytes) vía la fixture ``patched_key``, igual que ``test_security``.
"""

from __future__ import annotations

import base64
from uuid import UUID

import pytest
from cryptography.exceptions import InvalidTag

from app.core.config import Settings
from app.core.crypto import decrypt_for_user, encrypt_for_user

# 32 bytes deterministas (0..31) en base64: master key válido para los tests.
_VALID_KEY = base64.b64encode(bytes(range(32))).decode("ascii")

_USER_A = UUID(int=1)
_USER_B = UUID(int=2)

# Overhead fijo del blob: nonce (12) + auth_tag (16).
_OVERHEAD = 12 + 16


def _settings(master_key: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="x" * 40,
        MEMORY_ENCRYPTION_MASTER_KEY=master_key,
    )


@pytest.fixture
def patched_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(_VALID_KEY)
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: settings)


# ---------- roundtrip ----------


def test_roundtrip(patched_key: None) -> None:
    blob = encrypt_for_user(_USER_A, "un hecho semántico")
    assert decrypt_for_user(_USER_A, blob) == "un hecho semántico"


def test_ciphertext_is_not_plaintext(patched_key: None) -> None:
    blob = encrypt_for_user(_USER_A, "secreto")
    assert b"secreto" not in blob


def test_nonce_is_random(patched_key: None) -> None:
    # Mismo texto, misma key: dos blobs distintos (nonce fresco por record).
    a = encrypt_for_user(_USER_A, "mismo texto")
    b = encrypt_for_user(_USER_A, "mismo texto")
    assert a != b
    assert decrypt_for_user(_USER_A, a) == decrypt_for_user(_USER_A, b) == "mismo texto"


def test_blob_overhead_is_fixed(patched_key: None) -> None:
    plaintext = "hola"
    blob = encrypt_for_user(_USER_A, plaintext)
    assert len(blob) == len(plaintext.encode("utf-8")) + _OVERHEAD


# ---------- aislamiento por usuario / integridad ----------


def test_other_user_cannot_decrypt(patched_key: None) -> None:
    # Key derivada por usuario: el blob de A no es legible con la key de B.
    blob = encrypt_for_user(_USER_A, "privado de A")
    with pytest.raises(InvalidTag):
        decrypt_for_user(_USER_B, blob)


def test_tampered_ciphertext_rejected(patched_key: None) -> None:
    blob = bytearray(encrypt_for_user(_USER_A, "intacto"))
    blob[-1] ^= 0x01  # flip un bit del auth_tag
    with pytest.raises(InvalidTag):
        decrypt_for_user(_USER_A, bytes(blob))


def test_too_short_blob_rejected(patched_key: None) -> None:
    with pytest.raises(ValueError, match="demasiado corto"):
        decrypt_for_user(_USER_A, b"corto")


# ---------- edge cases de payload ----------


def test_empty_string_roundtrip(patched_key: None) -> None:
    blob = encrypt_for_user(_USER_A, "")
    assert decrypt_for_user(_USER_A, blob) == ""
    assert len(blob) == _OVERHEAD


def test_unicode_roundtrip(patched_key: None) -> None:
    text = "café ☕ ñandú 🧉 — voseo: ¿ejecutás? ¡sí!"
    blob = encrypt_for_user(_USER_A, text)
    assert decrypt_for_user(_USER_A, blob) == text


def test_large_payload_roundtrip(patched_key: None) -> None:
    text = "a" * (1024 * 1024 + 10)  # > 1 MB
    blob = encrypt_for_user(_USER_A, text)
    assert decrypt_for_user(_USER_A, blob) == text


# ---------- master key inválido ----------


def test_missing_master_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: _settings(""))
    with pytest.raises(RuntimeError, match="MEMORY_ENCRYPTION_MASTER_KEY no configurada"):
        encrypt_for_user(_USER_A, "x")


def test_invalid_base64_master_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: _settings("@@@no-base64@@@"))
    with pytest.raises(RuntimeError, match="no es base64"):
        encrypt_for_user(_USER_A, "x")


def test_wrong_length_master_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    short = base64.b64encode(bytes(16)).decode("ascii")  # 16 bytes != 32
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: _settings(short))
    with pytest.raises(RuntimeError, match="32 bytes"):
        encrypt_for_user(_USER_A, "x")


# ---------- regresión (sugeridos por el security review) ----------


def test_tampered_nonce_rejected(patched_key: None) -> None:
    # El nonce (primeros 12B) también está autenticado por GCM: flippearlo da InvalidTag.
    blob = bytearray(encrypt_for_user(_USER_A, "intacto"))
    blob[0] ^= 0x01
    with pytest.raises(InvalidTag):
        decrypt_for_user(_USER_A, bytes(blob))


def test_exact_overhead_garbage_rejected(patched_key: None) -> None:
    # 28 bytes (largo mínimo válido) de basura: pasa el check de largo pero GCM
    # lo rechaza con InvalidTag, no lo acepta como ct vacío.
    garbage = bytes(range(_OVERHEAD))
    with pytest.raises(InvalidTag):
        decrypt_for_user(_USER_A, garbage)


def test_error_does_not_leak_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regla #4: ante un error, el plaintext del usuario no debe aparecer en el mensaje.
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: _settings(""))
    secret = "dato-super-secreto-del-usuario"
    with pytest.raises(RuntimeError) as exc:
        encrypt_for_user(_USER_A, secret)
    assert secret not in str(exc.value)
