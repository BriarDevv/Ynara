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


def current_now(tz: str = APP_TIMEZONE) -> datetime:
    """Devuelve el ``datetime`` actual timezone-aware en el huso ``tz``.

    Único punto que lee el reloj (``datetime.now``); los callers (router / agent pass)
    lo usan para construir el preámbulo por-run. ``tz`` es un identificador IANA: el
    router baja el huso del usuario (``users.time_zone``) y la pasada del agente usa el
    default de la app (``APP_TIMEZONE``). El helper puro ``build_now_preamble`` recibe el
    ``now`` por parámetro y queda determinista.
    """
    return datetime.now(ZoneInfo(tz))


def _format_utc_offset(now: datetime) -> str:
    """Formatea el offset UTC de ``now`` como ``±HH:MM`` (p.ej. ``-03:00`` / ``+00:00``).

    Derivado de ``now.utcoffset()`` (no un literal): así el preámbulo refleja el huso
    REAL del usuario, no un ``-03:00`` hardcodeado de Argentina. Un ``now`` naive (sin
    tzinfo) cae a ``+00:00`` como fallback seguro.
    """
    offset = now.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "-" if total_minutes < 0 else "+"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def build_now_preamble(now: datetime, *, tz_label: str | None = None) -> str:
    """Arma la línea de fecha/hora actual en español a partir de ``now``.

    Determinista: solo depende de ``now`` (no toca el reloj). Los nombres de día y
    mes salen de tablas en español, no de ``strftime`` (que es locale-dependiente). El
    offset se DERIVA de ``now.utcoffset()`` (no un literal ``-03:00``), así un usuario en
    otro huso recibe su offset real.

    Args:
        now: ``datetime`` timezone-aware (ver ``current_now``). Se usan ``weekday()``,
            ``day``, ``month``, ``year``, ``hour``, ``minute`` y ``utcoffset()``.
        tz_label: etiqueta opcional del huso (p.ej. ``America/Argentina/Buenos_Aires``)
            para nombrarlo en la línea; ``None`` usa la frase genérica ``hora local``.

    Returns:
        Una línea del estilo::

            Fecha y hora actual: martes 22 de julio de 2026, 18:30 (hora local, offset
            UTC-03:00). Usala para resolver fechas relativas como 'mañana', 'el lunes',
            'en 2 horas'.
    """
    weekday = _WEEKDAYS_ES[now.weekday()]
    month = _MONTHS_ES[now.month]
    offset = _format_utc_offset(now)
    label = f"hora de {tz_label}" if tz_label else "hora local"
    # Nudge de huso (gotcha MEDIDO en E2E: qwen a veces emite la hora local con sufijo
    # 'Z' (UTC), corriendo el evento). Se instruye expresar las fechas accionadas con el
    # offset REAL del usuario (derivado de ``now``) para que el store guarde el instante
    # absoluto correcto sin importar si el modelo adjunta o no la zona.
    return (
        f"Fecha y hora actual: {weekday} {now.day} de {month} de {now.year}, "
        f"{now.hour:02d}:{now.minute:02d} ({label}, offset UTC{offset}). "
        "Usala para resolver fechas relativas como 'mañana', 'el lunes', 'en 2 horas'. "
        "Cuando agendes eventos o tareas, expresá las fechas (start_at / scheduled_at) en "
        f"hora local con el offset {offset} (formato ISO 8601, "
        f"p.ej. 2026-01-15T09:30:00{offset}); no uses 'Z' ni otro huso."
    )
