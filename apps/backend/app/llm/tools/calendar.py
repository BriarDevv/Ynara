"""Tools del namespace ``calendar`` (M6).

``CreateEventTool`` (``calendar.create_event``) y ``ListEventsTool``
(``calendar.list_events``). Validan sus argumentos con un modelo Pydantic v2
strict y devuelven un resultado STUB honesto: todavia no hay backend real de
calendario cableado. Los errores de validacion vuelven como dict
estructurado (``tool_error``), nunca como excepcion.

El JSON Schema OpenAI de cada tool se deriva del propio modelo Pydantic
(``tool_schema``), asi hay una sola fuente de verdad para validacion y para
lo que ve el modelo.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from app.llm.tools.base import (
    IsoDatetime,
    first_validation_error,
    not_wired_result,
    tool_error,
    tool_schema,
)

_NAMESPACE = "calendar"
_DETAIL = "calendar backend pendiente"


class _CreateEventArgs(BaseModel):
    """Argumentos de ``calendar.create_event`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: los ``datetime`` se mandan como strings
    ISO 8601 (tipo ``IsoDatetime``, que rechaza epoch numerico); el resto
    (``str``, ``list``) mantiene la validacion strict del modelo.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str
    start: IsoDatetime
    end: IsoDatetime
    attendees: list[str] | None = None


class _ListEventsArgs(BaseModel):
    """Argumentos de ``calendar.list_events`` (Pydantic v2 strict).

    ``from_dt`` / ``to_dt`` aceptan strings ISO 8601 (ver ``_CreateEventArgs``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: IsoDatetime
    to_dt: IsoDatetime


class CreateEventTool:
    """Agenda un evento en el calendario del usuario.

    TODO: cablear backend real (Google Calendar / CalDAV). Por ahora valida
    los argumentos y devuelve un stub estructurado.
    """

    name = f"{_NAMESPACE}.create_event"
    namespace = _NAMESPACE
    description = "Agenda un evento en el calendario del usuario."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_CreateEventArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _CreateEventArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)


class ListEventsTool:
    """Lista eventos del calendario en una ventana de tiempo.

    TODO: cablear backend real (Google Calendar / CalDAV). Por ahora valida
    los argumentos y devuelve un stub estructurado.
    """

    name = f"{_NAMESPACE}.list_events"
    namespace = _NAMESPACE
    description = "Lista eventos del calendario en una ventana de tiempo."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_ListEventsArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _ListEventsArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)
