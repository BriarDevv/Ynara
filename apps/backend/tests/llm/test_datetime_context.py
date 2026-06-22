"""Tests del helper de preámbulo de fecha/hora actual.

Cierra el gap E2E: el modelo NO tenía la fecha/hora en su contexto y no podía
resolver fechas relativas al agendar. El helper ``build_now_preamble`` es PURO y
DETERMINISTA (recibe ``now`` por parámetro), así que se testea con fechas fijas y se
verifica el string exacto, los nombres de día/mes en español y el zero-pad de la
hora. ``current_now()`` se verifica liviano: devuelve un ``datetime`` timezone-aware
en el huso de la app (sin afirmar el valor del reloj, que es no-determinista).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.llm.prompts.datetime_context import (
    APP_TIMEZONE,
    build_now_preamble,
    current_now,
)

_TZ = ZoneInfo(APP_TIMEZONE)


def test_build_now_preamble_exact_string() -> None:
    """Fecha fija -> string exacto esperado (determinista).

    2026-07-22 cae MIÉRCOLES (el día se deriva con ``weekday()``, no se hardcodea):
    el helper produce el nombre real del día, no el del ejemplo ilustrativo.
    """
    # miércoles 22 de julio de 2026, 18:30
    now = datetime(2026, 7, 22, 18, 30, tzinfo=_TZ)

    result = build_now_preamble(now)

    assert result == (
        "Fecha y hora actual: miércoles 22 de julio de 2026, 18:30 (hora de Argentina). "
        "Usala para resolver fechas relativas como 'mañana', 'el lunes', 'en 2 horas'. "
        "Cuando agendes eventos o tareas, expresá las fechas (start_at / scheduled_at) en "
        "hora local de Argentina con el offset -03:00 (formato ISO 8601, "
        "p.ej. 2026-01-15T09:30:00-03:00); no uses 'Z' ni otro huso."
    )


def test_build_now_preamble_zero_pads_hour_and_minute() -> None:
    """Hora/minuto de un dígito se rellenan a 2 dígitos (09:05, no 9:5)."""
    # lunes 5 de enero de 2026, 09:05
    now = datetime(2026, 1, 5, 9, 5, tzinfo=_TZ)

    result = build_now_preamble(now)

    assert "09:05" in result
    assert "lunes 5 de enero de 2026" in result


@pytest.mark.parametrize(
    ("date_args", "expected_weekday"),
    [
        ((2026, 6, 22), "lunes"),
        ((2026, 6, 23), "martes"),
        ((2026, 6, 24), "miércoles"),
        ((2026, 6, 25), "jueves"),
        ((2026, 6, 26), "viernes"),
        ((2026, 6, 27), "sábado"),
        ((2026, 6, 28), "domingo"),
    ],
)
def test_build_now_preamble_weekday_names_in_spanish(
    date_args: tuple[int, int, int], expected_weekday: str
) -> None:
    """Los 7 días de la semana salen en español (tabla determinista, no locale)."""
    now = datetime(*date_args, 12, 0, tzinfo=_TZ)
    assert build_now_preamble(now).startswith(f"Fecha y hora actual: {expected_weekday} ")


@pytest.mark.parametrize(
    ("month", "expected_name"),
    [
        (1, "enero"),
        (2, "febrero"),
        (3, "marzo"),
        (4, "abril"),
        (5, "mayo"),
        (6, "junio"),
        (7, "julio"),
        (8, "agosto"),
        (9, "septiembre"),
        (10, "octubre"),
        (11, "noviembre"),
        (12, "diciembre"),
    ],
)
def test_build_now_preamble_month_names_in_spanish(month: int, expected_name: str) -> None:
    """Los 12 meses salen en español (tabla determinista, no locale)."""
    now = datetime(2026, month, 15, 12, 0, tzinfo=_TZ)
    assert f"de {expected_name} de 2026" in build_now_preamble(now)


def test_build_now_preamble_includes_relative_date_hint() -> None:
    """El preámbulo instruye explícitamente a resolver fechas relativas."""
    result = build_now_preamble(datetime(2026, 7, 22, 18, 30, tzinfo=_TZ))
    assert "resolver fechas relativas" in result
    assert "mañana" in result


def test_current_now_is_timezone_aware_in_app_tz() -> None:
    """``current_now()`` devuelve un datetime aware en el huso de la app."""
    now = current_now()
    assert now.tzinfo is not None
    # El huso resuelto es el de Argentina (mismo que Celery).
    assert now.utcoffset() == datetime.now(_TZ).utcoffset()


def test_app_timezone_matches_celery() -> None:
    """El huso del helper es el MISMO que el de Celery (no divergir)."""
    assert APP_TIMEZONE == "America/Argentina/Buenos_Aires"
