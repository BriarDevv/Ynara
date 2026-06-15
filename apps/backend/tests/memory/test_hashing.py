"""Tests de ``app/memory/hashing.py``: digests deterministas para ``audit_log``.

Funciones puras, sin DB ni LLM. Lockean el contrato que ``audit_log`` (tabla
sagrada) y sus auditores asumen: 64 hex lowercase (CHECK
``record_hash_sha256_hex``), determinismo y la invariancia de ``sort_keys`` del
payload procedural.
"""

from __future__ import annotations

import re

from app.memory.hashing import compute_record_hash, procedural_hash_payload

# Mismo patrón que el CHECK ``ck_audit_log_record_hash_sha256_hex`` del modelo.
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def test_compute_record_hash_formato_sha256_hex() -> None:
    digest = compute_record_hash("hola mundo")
    assert _SHA256_HEX.fullmatch(digest), digest
    assert len(digest) == 64


def test_compute_record_hash_es_determinista() -> None:
    assert compute_record_hash("misma entrada") == compute_record_hash("misma entrada")


def test_compute_record_hash_distingue_inputs() -> None:
    assert compute_record_hash("a") != compute_record_hash("b")


def test_compute_record_hash_vector_conocido() -> None:
    # Vector estándar de sha256(""), para detectar cualquier cambio de algoritmo.
    assert compute_record_hash("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_procedural_payload_sort_keys_invariante() -> None:
    # El mismo par (key, value) con las claves del dict en distinto orden produce
    # EL MISMO payload (sort_keys) -> el mismo digest. Es la garantía de estabilidad.
    a = procedural_hash_payload("pref", {"tono": "formal", "idioma": "es"})
    b = procedural_hash_payload("pref", {"idioma": "es", "tono": "formal"})
    assert a == b
    assert compute_record_hash(a) == compute_record_hash(b)


def test_procedural_payload_incluye_key_y_json() -> None:
    payload = procedural_hash_payload("k1", {"x": 1})
    assert payload == 'k1\n{"x": 1}'


def test_procedural_payload_preserva_no_ascii() -> None:
    # ensure_ascii=False: los acentos NO se escapan a \\uXXXX (digest estable y legible).
    payload = procedural_hash_payload("nombre", {"valor": "café"})
    assert "café" in payload
    assert "\\u" not in payload


def test_procedural_payload_distingue_key() -> None:
    # Misma value, distinta key -> distinto payload (la key entra en el digest).
    assert procedural_hash_payload("k1", {"x": 1}) != procedural_hash_payload("k2", {"x": 1})
