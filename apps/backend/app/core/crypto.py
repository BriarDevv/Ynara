"""Cifrado de memoria a nivel campo (ADR-007 D3).

AES-256-GCM con una key derivada **por usuario** vía HKDF-SHA256 sobre un
master key server-side. Cifra el contenido textual de la memoria sagrada
(``semantic_memory.content`` y ``episodic_memory.summary``) para que un leak de
la DB (SQL injection, dump, backup robado) no exponga texto plano sin además el
master key + el ``user_id``.

Layout del blob (``BYTEA`` en la DB), overhead fijo de 28 bytes::

    nonce (12B) || ciphertext (var) || auth_tag (16B)

``AESGCM.encrypt`` ya concatena ``ciphertext || tag``, así que el blob es
``nonce || AESGCM.encrypt(...)``.

Blast radius acotado: comprometer la key derivada de un usuario no descifra a
los demás (cada uno tiene su ``info`` distinto en el HKDF). El único punto único
de falla es el master key: si se pierde, todo el contenido cifrado queda
irrecuperable (ADR-007, "Consecuencias negativas"). Backup en el gestor de
secretos del equipo, NUNCA en el repo (regla #2 de AGENTS.md).

El master key se lee de ``settings.memory_encryption_master_key`` (env
``MEMORY_ENCRYPTION_MASTER_KEY``, base64 de 32 bytes) de forma **lazy**: no se
toca al importar el módulo, solo al primer cifrado/descifrado. Si falta, se
levanta ``RuntimeError`` con un mensaje que NO incluye la key.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Sequence
from functools import lru_cache
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

__all__ = ["decrypt_for_user", "decrypt_many_for_user", "encrypt_for_user"]

_MASTER_KEY_BYTES = 32  # AES-256
_DERIVED_KEY_BYTES = 32  # AES-256
_NONCE_BYTES = 12  # GCM: nonce de 96 bits (recomendado)
_TAG_BYTES = 16  # GCM: auth tag de 128 bits
_HKDF_INFO_PREFIX = b"ynara-memory-v1:"  # versionado: permite rotar el esquema
_DERIVED_KEY_CACHE_SIZE = 2048  # keys derivadas residentes (LRU): cota del cache HKDF


@lru_cache(maxsize=4)
def _decode_master_key(b64_key: str) -> bytes:
    """Decodifica + valida el master key. Cacheado por valor (evita re-decodificar).

    Los mensajes de error nunca incluyen la key (regla #2 / #4).
    """
    try:
        raw = base64.b64decode(b64_key, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("MEMORY_ENCRYPTION_MASTER_KEY no es base64 válido") from exc
    if len(raw) != _MASTER_KEY_BYTES:
        raise RuntimeError(
            f"MEMORY_ENCRYPTION_MASTER_KEY debe decodificar a {_MASTER_KEY_BYTES} bytes "
            f"(AES-256); decodifica a {len(raw)}. Generar con `openssl rand -base64 32`."
        )
    return raw


def _master_key() -> bytes:
    b64_key = get_settings().memory_encryption_master_key
    if not b64_key:
        raise RuntimeError(
            "MEMORY_ENCRYPTION_MASTER_KEY no configurada: el cifrado de memoria no puede "
            "operar (ADR-007 D3). Generar con `openssl rand -base64 32` y setear en el .env."
        )
    return _decode_master_key(b64_key)


@lru_cache(maxsize=_DERIVED_KEY_CACHE_SIZE)
def _derive_key_cached(master_key: bytes, user_id: UUID) -> bytes:
    """HKDF-SHA256(master_key, info=user_id) cacheado por ``(master_key, user_id)``.

    Cachear sobre AMBOS — el master key Y el ``user_id`` — es deliberado: la key
    derivada depende de los dos, así que incluir el master en la clave del cache
    hace que un master rotado/ausente nunca devuelva una key vieja (un cambio de
    master produce otra entrada; si falta, ``_master_key`` levanta ANTES de llegar
    acá). El cache deja keys derivadas residentes en memoria, mismo perímetro de
    confianza que el master (ya residente); ``maxsize`` acota el crecimiento.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_DERIVED_KEY_BYTES,
        salt=None,
        info=_HKDF_INFO_PREFIX + str(user_id).encode("ascii"),
    )
    return hkdf.derive(master_key)


def _derive_key(user_id: UUID) -> bytes:
    """Deriva la key AES-256 del usuario vía HKDF-SHA256 sobre el master key.

    ``info`` liga la key a este ``user_id`` (y al schema v1): aísla el blast
    radius entre usuarios. Delega en ``_derive_key_cached`` para no re-correr
    HKDF-SHA256 en cada cifrado/descifrado del mismo usuario (SCAL-02): el cuello
    de botella del top-K de las búsquedas era re-derivar por record.
    """
    return _derive_key_cached(_master_key(), user_id)


def encrypt_for_user(user_id: UUID, plaintext: str) -> bytes:
    """Cifra ``plaintext`` para ``user_id``. Devuelve ``nonce || ciphertext || tag``.

    Nonce aleatorio de 96 bits por record (``os.urandom``): dos cifrados del
    mismo texto dan blobs distintos. No reutilizar nonce con la misma key es
    crítico en GCM — por eso uno fresco por llamada.
    """
    key = _derive_key(user_id)
    nonce = os.urandom(_NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + sealed


def decrypt_for_user(user_id: UUID, blob: bytes) -> str:
    """Descifra un blob de ``encrypt_for_user``. Devuelve el texto plano.

    Levanta ``cryptography.exceptions.InvalidTag`` si la key del usuario no
    corresponde o el ciphertext fue manipulado (GCM autentica), y ``ValueError``
    si el blob es más corto que el overhead mínimo (nonce + tag).
    """
    if len(blob) < _NONCE_BYTES + _TAG_BYTES:
        raise ValueError("blob de memoria demasiado corto: corrupto o no cifrado por Ynara")
    nonce, sealed = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    key = _derive_key(user_id)
    plaintext = AESGCM(key).decrypt(nonce, sealed, None)
    return plaintext.decode("utf-8")


def decrypt_many_for_user(user_id: UUID, blobs: Sequence[bytes]) -> list[str]:
    """Descifra un lote de blobs para ``user_id`` derivando la key UNA sola vez.

    Pensado para el top-K de las búsquedas ANN y los listados/export de memoria
    (``semantic``/``episodic``): deriva la key del usuario una vez (vía el cache
    de ``_derive_key``) y reutiliza una única instancia ``AESGCM`` para todo el
    lote, en lugar de re-derivar HKDF + reconstruir ``AESGCM`` por record. Es
    CPU-bound y las primitivas de OpenSSL liberan el GIL, así que el caller lo
    corre en un thread (``asyncio.to_thread``) para no bloquear el event loop
    bajo concurrencia (SCAL-02).

    Mismos modos de falla que ``decrypt_for_user``, por blob: ``InvalidTag`` si la
    key no corresponde o el ciphertext fue manipulado (GCM autentica), y
    ``ValueError`` si un blob es más corto que el overhead mínimo. Falla en el
    primer blob inválido (no descifra parcialmente un resultado corrupto).
    """
    key = _derive_key(user_id)
    aesgcm = AESGCM(key)
    plaintexts: list[str] = []
    for blob in blobs:
        if len(blob) < _NONCE_BYTES + _TAG_BYTES:
            raise ValueError("blob de memoria demasiado corto: corrupto o no cifrado por Ynara")
        nonce, sealed = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        plaintexts.append(aesgcm.decrypt(nonce, sealed, None).decode("utf-8"))
    return plaintexts
