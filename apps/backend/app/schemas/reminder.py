"""Schemas Pydantic del dominio de recordatorio (``Reminder``).

``ReminderOut`` es el recordatorio del wire — **no** filtra ``user_id`` /
``created_at`` / ``updated_at`` (mismo criterio que ``TaskOut`` / ``CalendarEventOut``).
``ReminderCreate`` es el alta del REST (``status`` lo fija el server en ``pending``);
``ReminderPatch`` es la edición parcial (``text`` / ``remind_at`` / ``status``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.enums import ReminderStatus
from app.schemas.base import YnaraBaseModel

# ``text`` no vacío + cota superior (1000): mismo criterio que ``Task.title`` en el REST
# (``min_length``, "Pydantic gana") pero CON techo, porque el endpoint REST también es
# user-fed (la tool del agente capa aparte en 200; ver ``_AgentSetReminderArgs``). La
# columna ``reminders.text`` es ``String(1000)``: el schema y la DB comparten la cota.
_Text = Annotated[str, Field(min_length=1, max_length=1000)]

# Los bodies de request reciben tipos del wire como strings JSON (``status`` str->enum,
# ``remind_at`` str->datetime). Bajo el ``strict=True`` heredado de ``YnaraBaseModel`` eso
# se rechaza, así que los schemas de request override-an ``strict=False`` a nivel modelo
# (MISMO patrón que ``TaskCreate`` / ``EventCreate``) manteniendo constraints +
# ``extra='forbid'``. ``ReminderOut`` (respuesta) hereda strict: ``ReminderStore._to_result``
# lo construye desde el ORM; el router lo re-hidrata desde el dict JSON-safe con
# ``strict=False`` puntual (mismo round-trip lossless que ``/tasks``).
_WIRE_REQUEST_CONFIG = ConfigDict(
    strict=False,
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)


class ReminderOut(YnaraBaseModel):
    """El recordatorio serializado para el wire.

    Mirror del modelo MENOS ``user_id`` / ``created_at`` / ``updated_at`` (no viajan).
    """

    id: UUID
    text: _Text
    remind_at: datetime
    status: ReminderStatus


class ReminderCreate(YnaraBaseModel):
    """Body de ``POST /v1/reminders`` (crear).

    Form mínimo: ``text`` + ``remind_at``. El ``status`` arranca ``pending`` en el server
    (no se acepta del body).
    """

    model_config = _WIRE_REQUEST_CONFIG

    text: _Text
    remind_at: datetime


class ReminderPatch(YnaraBaseModel):
    """Body de ``PATCH /v1/reminders/{id}`` (editar, parcial).

    Cualquier campo editable puede mandarse; los no enviados quedan intactos. ``status``
    solo acepta ``pending`` (re-activar) o ``cancelled``: ``sent`` es server-only (lo fija
    el scheduler al despachar), ver ``_reject_sent_status``.
    """

    model_config = _WIRE_REQUEST_CONFIG

    text: _Text | None = None
    remind_at: datetime | None = None
    status: ReminderStatus | None = None

    @field_validator("status")
    @classmethod
    def _reject_sent_status(cls, value: ReminderStatus | None) -> ReminderStatus | None:
        """``sent`` NO es seteable por el usuario (solo el scheduler, al despachar).

        Permitirlo abre un double-dispatch: un PATCH a ``pending`` sobre un recordatorio
        ya ``sent`` con ``remind_at`` pasado lo re-despacharía en el próximo scan. El PATCH
        solo admite ``pending`` (re-activar) o ``cancelled``; ``sent`` → 422.

        Se usa ``PydanticCustomError`` (no un ``ValueError`` pelado), MISMO patrón que
        ``UserUpdate.time_zone`` / ``EventCreate``: el handler de ``RequestValidationError``
        en ``app/main.py`` serializa con ``json.dumps`` directo, y un ``ValueError`` crudo
        viaja en el ``ctx`` como objeto NO serializable (rompe la respuesta). El custom error
        lleva solo ``type``/``msg`` estables, sin datos del usuario (regla #4).
        """
        if value is ReminderStatus.SENT:
            raise PydanticCustomError(
                "reminder_status_not_settable",
                "status 'sent' no es seteable; lo fija el scheduler.",
            )
        return value
