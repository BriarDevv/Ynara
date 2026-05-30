"""Ensamblador de system prompts por modo.

``load_prompt(mode)`` arma el prompt final concatenando los fragmentos
compartidos (identidad, voz, seguridad) con el ``SYSTEM_PROMPT`` del modo
pedido. El resultado se cachea con ``lru_cache`` porque los prompts son
estaticos: no dependen del usuario ni de la sesion (la memoria viva la inyecta
el router en M8, no este loader).

Si el modo no tiene prompt registrado, levanta ``ValueError`` con el nombre del
modo. El mapa ``_MODE_PROMPTS`` es la fuente de verdad de que modos estan
cubiertos; el test de regresion verifica que cubra todos los miembros de
``Mode``.
"""

from __future__ import annotations

from functools import lru_cache

from app.enums import Mode
from app.llm.prompts import bienestar, estudio, memoria, productividad, vida
from app.llm.prompts.shared import (
    IDENTITY_FRAGMENT,
    SAFETY_FRAGMENT,
    VOICE_FRAGMENT,
)

# Mapa modo -> SYSTEM_PROMPT del modo. Unica fuente de verdad de la cobertura.
_MODE_PROMPTS: dict[Mode, str] = {
    Mode.PRODUCTIVIDAD: productividad.SYSTEM_PROMPT,
    Mode.ESTUDIO: estudio.SYSTEM_PROMPT,
    Mode.BIENESTAR: bienestar.SYSTEM_PROMPT,
    Mode.VIDA: vida.SYSTEM_PROMPT,
    Mode.MEMORIA: memoria.SYSTEM_PROMPT,
}

# Orden de los fragmentos compartidos que anteceden al prompt de modo.
_SHARED_FRAGMENTS: tuple[str, ...] = (
    IDENTITY_FRAGMENT,
    VOICE_FRAGMENT,
    SAFETY_FRAGMENT,
)


@lru_cache(maxsize=len(Mode))
def load_prompt(mode: Mode) -> str:
    """Devuelve el system prompt completo y estatico para ``mode``.

    Concatena identidad + voz + seguridad + el prompt especifico del modo,
    separados por linea en blanco. Cacheado: la misma entrada devuelve siempre
    el mismo string.

    Raises:
        ValueError: si ``mode`` no tiene un ``SYSTEM_PROMPT`` registrado.
    """
    try:
        mode_prompt = _MODE_PROMPTS[mode]
    except KeyError as exc:
        raise ValueError(f"no hay system prompt para el modo: {mode!r}") from exc

    sections = (*_SHARED_FRAGMENTS, mode_prompt)
    return "\n\n".join(sections)
