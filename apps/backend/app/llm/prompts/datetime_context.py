"""Preámbulo de fecha/hora actual para inyectar en el system prompt del LLM.

GAP que cierra (verificación E2E): el modelo NO tenía la fecha/hora actual en su
contexto, así que NO podía resolver fechas relativas ("mañana", "el lunes", "en 2
horas") al agendar. En la prueba en vivo, "agendame gym mañana 18hs" hizo que qwen
pidiera la fecha en vez de agendar. Este módulo arma una línea en español que el
router (chat) y la pasada del agente anteponen al system prompt para que el modelo
ancle las fechas relativas contra el "ahora" real.

DISEÑO (puro y testeable):
- ``build_now_preamble(now)`` recibe el ``datetime`` por parámetro: es DETERMINISTA
  (no toca el reloj), así el test fija una fecha y verifica el string exacto. Los
  nombres de día/mes se arman con tablas explícitas en español (NO ``strftime`` con
  locale, que es no-determinista entre entornos y suele no estar en español).
- ``current_now()`` es el único punto que lee el reloj: devuelve un ``datetime``
  timezone-aware en el huso de la app (``America/Argentina/Buenos_Aires``, el mismo
  que usa Celery en ``app/workers/celery_app.py``). Lo usan los callers (router /
  agent pass); el helper puro queda intacto para los tests.

El string NO se cachea (cambia cada minuto) y se construye por-run: el router lo
concatena en un STRING NUEVO (no muta el prompt cacheado) y la pasada del agente lo
arma por corrida (no como constante estática).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

__all__ = ["APP_TIMEZONE", "build_now_preamble", "current_now"]

# Huso de la app: el MISMO que Celery (``app/workers/celery_app.py`` conf.timezone).
# Las fechas relativas que el usuario dice ("mañana", "el lunes") se interpretan en
# hora local de Argentina, no en UTC.
APP_TIMEZONE = "America/Argentina/Buenos_Aires"

# Nombres en español, indexados por el resultado de ``datetime`` (determinista, sin
# depender del locale del sistema). ``weekday()``: lunes=0 .. domingo=6. ``month``:
# enero=1 .. diciembre=12 (índice 0 sin usar para alinear con el número de mes).
_WEEKDAYS_ES: tuple[str, ...] = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_MONTHS_ES: tuple[str, ...] = (
    "",  # índice 0 sin usar: los meses van 1..12
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def current_now() -> datetime:
    """Devuelve el ``datetime`` actual timezone-aware en el huso de la app.

    Único punto que lee el reloj (``datetime.now``); los callers (router / agent
    pass) lo usan para construir el preámbulo por-run. El helper puro
    ``build_now_preamble`` recibe el ``now`` por parámetro y queda determinista.
    """
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def build_now_preamble(now: datetime) -> str:
    """Arma la línea de fecha/hora actual en español a partir de ``now``.

    Determinista: solo depende de ``now`` (no toca el reloj). Los nombres de día y
    mes salen de tablas en español, no de ``strftime`` (que es locale-dependiente).

    Args:
        now: ``datetime`` (idealmente timezone-aware, ver ``current_now``). Se usan
            ``weekday()``, ``day``, ``month``, ``year``, ``hour`` y ``minute``.

    Returns:
        Una línea del estilo::

            Fecha y hora actual: martes 22 de julio de 2026, 18:30 (hora de
            Argentina). Usala para resolver fechas relativas como 'mañana', 'el
            lunes', 'en 2 horas'.
    """
    weekday = _WEEKDAYS_ES[now.weekday()]
    month = _MONTHS_ES[now.month]
    return (
        f"Fecha y hora actual: {weekday} {now.day} de {month} de {now.year}, "
        f"{now.hour:02d}:{now.minute:02d} (hora de Argentina). "
        "Usala para resolver fechas relativas como 'mañana', 'el lunes', 'en 2 horas'."
    )
