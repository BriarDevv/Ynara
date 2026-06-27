"""Validación de identificadores de huso horario IANA — sede única.

Antes vivía como helper privado ``_check_time_zone_iana`` de
``app/llm/tools/calendar.py`` (boundary leak). Acá es la API pública compartida por
TODOS los boundaries que aceptan un ``time_zone`` del exterior: los schemas Pydantic
del usuario (``app/schemas/user.py``) y las tool args del agente
(``app/llm/tools/calendar.py``). Una sola sede para "qué es un huso válido" evita
que cada boundary re-implemente la regla con criterios distintos (DRY).

Regla #4: el mensaje de error NUNCA arrastra el valor inválido recibido (un string
arbitrario del usuario / del LLM), solo una etiqueta técnica corta.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = ["validate_iana_tz"]


def validate_iana_tz(value: str) -> str:
    """Valida que ``value`` sea un identificador IANA válido; devuelve el mismo string.

    Construye el ``ZoneInfo`` correspondiente: si el string no es un identificador IANA
    real (p.ej. ``"UTC+3"``, ``"Argentina"`` a secas o cualquier string arbitrario),
    ``ZoneInfo`` levanta ``ZoneInfoNotFoundError`` (o ``ValueError``/``KeyError`` para
    keys malformadas con ``..`` u otros). En cualquier caso se re-lanza un ``ValueError``
    con un mensaje técnico que NO incluye el valor inválido (regla #4); el caller (schema
    Pydantic o tool) lo envuelve en el error estructurado que corresponda.

    Returns:
        El mismo ``value`` si es un huso IANA válido.

    Raises:
        ValueError: si ``value`` no es un identificador IANA parseable.
    """
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        # ``from None``: corta el encadenamiento para que el traceback NO arrastre el
        # valor inválido a los logs (regla #4).
        raise ValueError("time_zone debe ser un identificador IANA válido.") from None
    return value
