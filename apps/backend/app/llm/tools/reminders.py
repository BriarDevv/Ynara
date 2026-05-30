"""Tools del namespace ``reminders`` (M6).

``SetReminderTool`` (``reminder.set``) y ``ListRemindersTool``
(``reminder.list``). Mismo patron que ``calendar.py``: validan con Pydantic
v2 strict y devuelven un stub honesto, porque todavia no existe la tabla
``reminders`` ni un backend real.

Nota de naming: el namespace de habilitacion por modo es ``reminders``
(plural, como en ``ynara.config.json``), pero el ``name`` de cada tool usa
el prefijo ``reminder`` (singular, como en ``docs/TOOLS.md``:
``reminder.set``). Por eso ``namespace`` se declara aparte y no se deriva
del prefijo del ``name``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.tools.base import tool_error

_NAMESPACE = "reminders"


def _stub_result(action: str, arguments: dict[str, object]) -> dict[str, object]:
    """Resultado stub uniforme: honesto sobre que no hay backend real."""
    return {
        "status": "not_wired",
        "detail": "reminders backend pendiente",
        "action": action,
        "echo": arguments,
    }


class _SetReminderArgs(BaseModel):
    """Argumentos de ``reminder.set`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: ``when`` se manda como string ISO 8601,
    asi que va ``strict=False`` para coercer la string; ``text`` mantiene la
    validacion strict.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    text: str
    when: datetime = Field(strict=False)


class _ListRemindersArgs(BaseModel):
    """Argumentos de ``reminder.list`` (Pydantic v2 strict).

    Ventana opcional: sin argumentos lista todos los recordatorios activos.
    ``from_dt`` / ``to_dt`` aceptan strings ISO 8601 (ver ``_SetReminderArgs``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: datetime | None = Field(default=None, strict=False)
    to_dt: datetime | None = Field(default=None, strict=False)


class SetReminderTool:
    """Crea un recordatorio.

    TODO: cablear backend real (tabla ``reminders`` + scheduler). Por ahora
    valida los argumentos y devuelve un stub estructurado.
    """

    name = "reminder.set"
    namespace = _NAMESPACE
    description = "Crea un recordatorio para una fecha y hora."

    @property
    def parameters(self) -> dict[str, object]:
        return _SetReminderArgs.model_json_schema()

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _SetReminderArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", _first_error(exc))
        return _stub_result(self.name, validated.model_dump(mode="json"))


class ListRemindersTool:
    """Lista los recordatorios del usuario.

    TODO: cablear backend real (tabla ``reminders``). Por ahora valida los
    argumentos y devuelve un stub estructurado.
    """

    name = "reminder.list"
    namespace = _NAMESPACE
    description = "Lista los recordatorios del usuario."

    @property
    def parameters(self) -> dict[str, object]:
        return _ListRemindersArgs.model_json_schema()

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _ListRemindersArgs.model_validate(arguments)
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
