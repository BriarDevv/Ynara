"""Utilidades de texto compartidas de la capa LLM.

Helpers puros (sin estado, sin IO) para procesar el ``text`` crudo que devuelve
un modelo. Vive acá (y NO como un ``_private`` de ``memory_engine``) para que
otros consumidores (p.ej. el playground admin, F1 ADR-018) puedan separar el
bloque de razonamiento sin acoplarse a un internal del motor de memoria.

Qwen es un modelo *thinking*: su razonamiento llega embebido en ``text`` como un
bloque ``<think>...</think>`` (default del server / Ollama sin reasoning-parser).
``THINK_BLOCK_RE`` matchea ese bloque y ``split_thinking`` lo separa del texto
limpio.
"""

from __future__ import annotations

import re

# Bloque de razonamiento ``<think>...</think>`` que algunos servers anteponen al
# ``text`` (Qwen thinking model / Ollama sin reasoning-parser). DOTALL para que
# ``.`` cruce saltos de línea; IGNORECASE por si el tag viene en mayúsculas.
THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)


def split_thinking(text: str) -> tuple[str, str | None]:
    """Separa el bloque ``<think>...</think>`` del texto limpio.

    Devuelve ``(clean_text, thinking)`` donde ``clean_text`` es ``text`` sin el
    bloque de razonamiento (con los bordes recortados) y ``thinking`` es el bloque
    crudo (incluyendo los tags) o ``None`` si no hay ninguno.

    No falla nunca: si ``text`` no tiene ``<think>``, devuelve ``(text.strip(),
    None)``.
    """
    match = THINK_BLOCK_RE.search(text)
    thinking = match.group(0) if match else None
    clean_text = THINK_BLOCK_RE.sub("", text).strip()
    return clean_text, thinking
