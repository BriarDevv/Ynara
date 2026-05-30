"""Prompt templates de Ynara.

Convencion: un archivo por modo (``productividad.py``, ``estudio.py``,
``bienestar.py``, ``vida.py``, ``memoria.py``), cada uno expone una constante
``SYSTEM_PROMPT``; ``shared.py`` con fragmentos comunes (identidad, voz,
seguridad); ``loader.py`` ensambla el prompt final por modo.

Los prompts se versionan con commits; cualquier cambio significativo debe poder
reproducirse con el test de regresion en ``tests/llm/test_prompts.py``.

Uso:

    from app.llm.prompts import load_prompt
    from app.enums import Mode

    system = load_prompt(Mode.PRODUCTIVIDAD)
"""

from __future__ import annotations

from app.llm.prompts.loader import load_prompt
from app.llm.prompts.shared import (
    IDENTITY_FRAGMENT,
    SAFETY_FRAGMENT,
    VOICE_FRAGMENT,
)

__all__ = [
    "IDENTITY_FRAGMENT",
    "SAFETY_FRAGMENT",
    "VOICE_FRAGMENT",
    "load_prompt",
]
