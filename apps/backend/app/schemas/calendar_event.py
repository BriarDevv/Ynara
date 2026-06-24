"""Schemas Pydantic del dominio de evento de agenda (``CalendarEvent``).

Espejan el contrato de ``packages/shared-schemas/src/agenda.ts`` ("Pydantic gana,
Zod sigue"): mismos campos snake_case, mismas validaciones. ``CalendarEventOut``
es el ``AgendaEvent`` del wire — **no** filtra ``user_id`` / ``created_at`` /
``updated_at`` (a diferencia de ``SessionOut``, que sí los expone): el front no
los necesita y el contrato del front no los declara.

Invariante ADR-023 (``recurrenceNeedsTimeZone`` en ``agenda.ts``): un evento con
``recurrence`` no vacía DEBE traer ``time_zone``. Se valida en ``CalendarEventOut``
y ``EventCreate``, **no** en ``EventPatch`` (parcial; el patch puede tocar
``recurrence`` apoyándose en el ``time_zone`` ya guardado). El router enforcea la
invariante sobre el **estado MERGEADO** de un PATCH (ver ``app/api/v1/events.py``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.enums import EventStatus, Mode
from app.schemas.base import YnaraBaseModel

# Mirror de las validaciones de ``agenda.ts``: ``title`` no vacío y ``duration_min``
# entero positivo (``z.string().min(1)`` / ``z.number().int().positive()``).
_Title = Annotated[str, Field(min_length=1)]
_DurationMin = Annotated[int, Field(gt=0)]

# Los bodies de request reciben tipos del wire como strings JSON (``start_at``
# str->datetime, ``mode``/``status`` str->enum) y FastAPI valida el ``dict`` ya
# parseado. Bajo el ``strict=True`` heredado de ``YnaraBaseModel`` eso se rechaza
# (un ``str`` no es instancia de ``datetime``/``Mode``/``EventStatus``), así que los
# schemas de request override-an ``strict=False`` a nivel modelo —MISMO patrón que
# ``ChatHttpRequest`` / los de ``auth.py``— manteniendo constraints + ``extra='forbid'``.
# ``CalendarEventOut`` (respuesta, construida desde el ORM con tipos reales) sigue strict.
_WIRE_REQUEST_CONFIG = ConfigDict(
    strict=False,
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)


def _validate_recurrence_needs_time_zone(
    recurrence: list[str] | None, time_zone: str | None
) -> None:
    """Invariante ADR-023: ``recurrence`` no vacía exige ``time_zone``.

    Lanza ``PydanticCustomError`` (que Pydantic convierte en 422) si hay recurrencia
    sin huso. Sede única de la regla, compartida por ``CalendarEventOut`` /
    ``EventCreate`` y por el router (estado mergeado del PATCH).

    Se usa ``PydanticCustomError`` (no un ``ValueError`` pelado) a propósito: el
    handler de ``RequestValidationError`` en ``app/main.py`` serializa el error con
    ``json.dumps`` directo, y un ``ValueError`` crudo viaja en el ``ctx`` como objeto
    NO serializable (rompe la respuesta). ``PydanticCustomError`` produce un error con
    ``type`` estable (``recurrence_needs_time_zone``) y ``msg`` ya serializables.
    """
    if recurrence and not time_zone:
        raise PydanticCustomError(
            "recurrence_needs_time_zone",
            "time_zone es obligatorio en eventos con recurrence.",
        )


class CalendarEventOut(YnaraBaseModel):
    """El evento serializado para el wire (el ``AgendaEvent`` del front).

    Mirror del modelo MENOS ``user_id`` / ``created_at`` / ``updated_at`` (no
    viajan: el contrato del front no los declara). El fin del bloque es derivado
    (``start_at + duration_min``), no un campo.
    """

    id: UUID
    title: _Title
    start_at: datetime
    duration_min: _DurationMin
    mode: Mode | None
    status: EventStatus
    location: str | None
    time_zone: str | None
    all_day: bool
    recurrence: list[str] | None

    @model_validator(mode="after")
    def _check_recurrence_time_zone(self) -> CalendarEventOut:
        _validate_recurrence_needs_time_zone(self.recurrence, self.time_zone)
        return self


class EventCreate(YnaraBaseModel):
    """Body de ``POST /v1/events`` (crear).

    Form mínimo: ``title`` + ``start_at`` + ``duration_min``. ``mode`` /
    ``location`` / ``time_zone`` / ``recurrence`` son opcionales (default
    ``None``); ``all_day`` default ``False``. El ``status`` arranca ``confirmed``
    en el server (no se acepta del body). El fin es derivado.
    """

    model_config = _WIRE_REQUEST_CONFIG

    title: _Title
    start_at: datetime
    duration_min: _DurationMin
    mode: Mode | None = None
    location: str | None = None
    time_zone: str | None = None
    all_day: bool = False
    recurrence: list[str] | None = None

    @model_validator(mode="after")
    def _check_recurrence_time_zone(self) -> EventCreate:
        _validate_recurrence_needs_time_zone(self.recurrence, self.time_zone)
        return self


class EventPatch(YnaraBaseModel):
    """Body de ``PATCH /v1/events/{id}`` (editar, parcial).

    Cualquier campo editable puede mandarse; los no enviados quedan intactos. NO
    valida la invariante ``recurrence``/``time_zone`` acá (es parcial): el router
    la enforcea sobre el estado MERGEADO (la fila ya guardada + el patch).
    """

    model_config = _WIRE_REQUEST_CONFIG

    title: _Title | None = None
    start_at: datetime | None = None
    duration_min: _DurationMin | None = None
    mode: Mode | None = None
    status: EventStatus | None = None
    location: str | None = None
    time_zone: str | None = None
    all_day: bool | None = None
    recurrence: list[str] | None = None
