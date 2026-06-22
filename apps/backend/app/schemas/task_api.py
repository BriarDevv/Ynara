"""Wrappers de respuesta de la API ``/v1/tasks`` (NO sagrados).

Envelope del wire HTTP de ``GET /v1/tasks``. **No** es una tabla ni espeja el
modelo: solo agrupa los ``TaskOut`` de ``app/schemas/task.py``, que se reusan tal
cual como ``items``. Mismo patrón (y nombres del contrato) que
``TasksResponseSchema`` en ``packages/shared-schemas/src/today.ts``.

Separación deliberada (igual que ``calendar_event_api.py`` / ``session_api.py``): el
``*Out`` mirror del modelo vive en ``task.py`` y el envelope de presentación
(``items`` + ``total``) vive acá, en un archivo de wrappers que no toca el contrato
de la tarea.
"""

from __future__ import annotations

from app.schemas.base import YnaraBaseModel
from app.schemas.task import TaskOut


class TasksResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/tasks``: los ``items`` + el ``total`` del user.

    ``items`` son las tareas del usuario (pending primero, luego por
    ``scheduled_at`` asc); ``total`` es el conteo COMPLETO de tareas del user.
    Espeja ``TasksResponseSchema`` del front (``useTasks()`` toma ``.items``).
    """

    items: list[TaskOut]
    total: int
