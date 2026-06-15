"""Digests deterministas para el ``record_hash`` de ``audit_log`` (tabla sagrada).

Módulo de funciones puras (solo stdlib): NO toca SQL ni el LLM. Es la **sede
única** del formato de los digests de auditoría, compartida por el motor de
extracción de memoria (``app/llm/memory_engine.py``), los endpoints de memoria
(``app/api/v1/memory.py``) y sus tests. Antes vivían como helpers privados de
``memory_engine`` y la API los importaba con el guión bajo (boundary leak); ahora
son la API pública de este módulo neutral.

REGLA #4: el digest es unidireccional — ``audit_log`` guarda el hash, NUNCA el
contenido en claro.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_record_hash(value: str) -> str:
    """sha256 hex (64 chars) del valor para el ``record_hash`` de ``audit_log``.

    REGLA #4: el digest es unidireccional — la fila de auditoría guarda este
    hash, NO el contenido en claro. Siempre devuelve 64 chars ``[0-9a-f]``, así
    que el CHECK ``record_hash_sha256_hex`` del modelo nunca falla.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def procedural_hash_payload(key: str, value: dict[str, Any]) -> str:
    """Payload canónico ``(key, value)`` para el ``record_hash`` procedural.

    Sede ÚNICA del formato del digest procedural: el ``value`` se serializa con
    ``sort_keys`` para que el mismo par dé siempre el mismo hash, independiente
    del orden de las claves del dict. El resultado se pasa por
    ``compute_record_hash`` para obtener el digest final.
    """
    return f"{key}\n{json.dumps(value, sort_keys=True, ensure_ascii=False)}"
