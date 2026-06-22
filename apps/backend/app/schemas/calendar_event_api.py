"""Wrappers de respuesta de la API ``/v1/events`` (NO sagrados).

Envelope del wire HTTP de ``GET /v1/events``. **No** es una tabla ni espeja el
modelo: solo agrupa los ``CalendarEventOut`` de ``app/schemas/calendar_event.py``,
que se reusan tal cual como ``items``. Mismo patrón (y nombres del contrato) que
``EventsResponseSchema`` en ``packages/shared-schemas/src/agenda.ts``.

Separación deliberada (igual que ``session_api.py`` / ``memory_api.py``): el
``*Out`` mirror del modelo vive en ``calendar_event.py`` y el envelope de
presentación (``items`` + ``total``) vive acá, en un archivo de wrappers que no
toca el contrato del evento.
"""

from __future__ import annotations

from app.schemas.base import YnaraBaseModel
from app.schemas.calendar_event import CalendarEventOut


class EventsResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/events``: los ``items`` + el ``total`` del user.

    ``items`` son los eventos del usuario (ordenados por ``start_at`` ASC);
    ``total`` es el conteo COMPLETO de eventos del user. Espeja
    ``EventsResponseSchema`` del front.
    """

    items: list[CalendarEventOut]
    total: int
