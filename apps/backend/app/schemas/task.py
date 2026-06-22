"""Schemas Pydantic del dominio de tarea/prioridad del día (``Task``).

Espejan el contrato de ``packages/shared-schemas/src/today.ts`` ("Pydantic gana,
Zod sigue"): mismos campos snake_case, mismas validaciones. ``TaskOut`` es el
``Task`` del wire — **no** filtra ``user_id`` / ``created_at`` / ``updated_at``
(igual que ``CalendarEventOut``): el front no los necesita y el contrato del front
no los declara.

A diferencia de Agenda, NO hay invariante recurrence/time_zone (el modelo de tareas
es más simple): ``scheduled_at`` y ``duration_min`` son nullable y no se condicionan
entre sí. ``TaskPatch`` togglea SOLO ``status`` (la rama mínima del futuro
``TaskUpdate``, ver ``TaskPatchSchema`` en ``today.ts``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from app.enums import TaskStatus
from app.schemas.base import YnaraBaseModel

# Mirror de las validaciones de ``today.ts``: ``title`` no vacío
# (``z.string().min(1)``) y ``duration_min`` entero positivo
# (``z.number().int().positive()``), pero NULLABLE en el modelo de tareas.
_Title = Annotated[str, Field(min_length=1)]
_DurationMin = Annotated[int, Field(gt=0)]

# Los bodies de request reciben tipos del wire como strings JSON (``status``
# str->enum, ``scheduled_at`` str->datetime) y FastAPI valida el ``dict`` ya
# parseado. Bajo el ``strict=True`` heredado de ``YnaraBaseModel`` eso se rechaza
# (un ``str`` no es instancia de ``datetime``/``TaskStatus``), así que los schemas
# de request override-an ``strict=False`` a nivel modelo —MISMO patrón que
# ``EventCreate`` / ``ChatHttpRequest``— manteniendo constraints + ``extra='forbid'``.
# ``TaskOut`` (respuesta) hereda strict: ``TaskStore._to_result`` lo construye desde el
# ORM (tipos reales, strict OK). El router HTTP, en cambio, lo re-hidrata desde el dict
# JSON-safe que devuelve el store (id/status/scheduled_at como str, porque el mismo store
# alimenta el tool loop del agente): ese único caso re-valida con ``strict=False`` (ver
# ``app/api/v1/tasks.py``); el round-trip es lossless porque el dict ya es un ``TaskOut``.
_WIRE_REQUEST_CONFIG = ConfigDict(
    strict=False,
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)


class TaskOut(YnaraBaseModel):
    """La tarea serializada para el wire (el ``Task`` del front).

    Mirror del modelo MENOS ``user_id`` / ``created_at`` / ``updated_at`` (no
    viajan: el contrato del front no los declara). ``scheduled_at`` /
    ``duration_min`` son nullable (una prioridad puede no tener horario).
    """

    id: UUID
    title: _Title
    status: TaskStatus
    scheduled_at: datetime | None
    duration_min: _DurationMin | None


class TaskCreate(YnaraBaseModel):
    """Body de ``POST /v1/tasks`` (crear).

    Form mínimo: ``title``. ``scheduled_at`` / ``duration_min`` son opcionales
    (default ``None``). El ``status`` arranca ``pending`` en el server (no se acepta
    del body). No hay invariante entre campos (a diferencia de Agenda).
    """

    model_config = _WIRE_REQUEST_CONFIG

    title: _Title
    scheduled_at: datetime | None = None
    duration_min: _DurationMin | None = None


class TaskPatch(YnaraBaseModel):
    """Body de ``PATCH /v1/tasks/{id}`` (togglear estado).

    Por ahora SOLO togglea ``status`` (marcar hecha / re-abrir desde el check del
    front, ``TaskPatchSchema`` en ``today.ts``). ``status`` es REQUERIDO (el front
    siempre manda el estado opuesto): no es un patch parcial multi-campo como
    ``EventPatch``, es el toggle mínimo del wireframe.
    """

    model_config = _WIRE_REQUEST_CONFIG

    status: TaskStatus
