"""Wrappers de respuesta de la API ``/v1/reminders`` (NO sagrados).

Envelope del wire HTTP de ``GET /v1/reminders``. **No** es una tabla ni espeja el
modelo: solo agrupa los ``ReminderOut`` de ``app/schemas/reminder.py``, que se reusan tal
cual como ``items``. Mismo patrón que ``calendar_event_api.py`` / ``task_api.py``.
"""

from __future__ import annotations

from app.schemas.base import YnaraBaseModel
from app.schemas.reminder import ReminderOut


class RemindersResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/reminders``: los ``items`` + el ``total`` del user.

    ``items`` son los recordatorios del usuario (ordenados por ``remind_at`` ASC);
    ``total`` es el conteo COMPLETO de recordatorios del user (para paginar).
    """

    items: list[ReminderOut]
    total: int
