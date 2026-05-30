"""Tools del namespace ``calendar`` (M6).

``CreateEventTool`` (``calendar.create_event``) y ``ListEventsTool``
(``calendar.list_events``). Validan sus argumentos con un modelo Pydantic v2
strict y devuelven un resultado STUB honesto: todavia no hay backend real de
calendario cableado. Los errores de validacion vuelven como dict
estructurado (``tool_error``), nunca como excepcion.

El JSON Schema OpenAI de cada tool se deriva del propio modelo Pydantic
(``model_json_schema``), asi hay una sola fuente de verdad para validacion y
para lo que ve el modelo.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.tools.base import tool_error

_NAMESPACE = "calendar"


def _stub_result(action: str, arguments: dict[str, object]) -> dict[str, object]:
    """Resultado stub uniforme: honesto sobre que no hay backend real."""
    return {
        "status": "not_wired",
        "detail": "calendar backend pendiente",
        "action": action,
        "echo": arguments,
    }


class _CreateEventArgs(BaseModel):
    """Argumentos de ``calendar.create_event`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: los ``datetime`` se mandan como strings
    ISO 8601, asi que esos campos van ``strict=False`` para coercer la string;
    el resto (``str``, ``list``) mantiene la validacion strict del modelo.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str
    start: datetime = Field(strict=False)
    end: datetime = Field(strict=False)
    attendees: list[str] | None = None


class _ListEventsArgs(BaseModel):
    """Argumentos de ``calendar.list_events`` (Pydantic v2 strict).

    ``from_dt`` / ``to_dt`` aceptan strings ISO 8601 (ver ``_CreateEventArgs``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: datetime = Field(strict=False)
    to_dt: datetime = Field(strict=False)


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
        return _CreateEventArgs.model_json_schema()

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _CreateEventArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", _first_error(exc))
        return _stub_result(self.name, validated.model_dump(mode="json"))


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
        return _ListEventsArgs.model_json_schema()

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _ListEventsArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", _first_error(exc))
        return _stub_result(self.name, validated.model_dump(mode="json"))


def _first_error(exc: ValidationError) -> str:
    """Etiqueta tecnica corta del primer error, sin volcar el input.

    No incluimos el valor recibido (regla #4: nada de datos del usuario en
    el texto): solo la ubicacion del campo y el tipo de error.
    """
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"]) or "(root)"
    return f"argumento invalido en '{loc}': {err['type']}"
