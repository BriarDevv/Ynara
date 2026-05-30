"""Tools del namespace ``reminder`` (M6).

``SetReminderTool`` (``reminder.set``) y ``ListRemindersTool``
(``reminder.list``). Mismo patron que ``calendar.py``: validan con Pydantic
v2 strict y devuelven un stub honesto, porque todavia no existe la tabla de
recordatorios ni un backend real.

Naming unificado en singular ``reminder`` (alineado con ``calendar`` y
``docs/TOOLS.md``): el namespace de habilitacion por modo
(``ynara.config.json[modes][*].tools_enabled``), el prefijo de los ``name``
(``reminder.set`` / ``reminder.list``) y este modulo son todos singulares.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from app.llm.tools.base import IsoDatetime, tool_error

_NAMESPACE = "reminder"


def _stub_result(action: str, arguments: dict[str, object]) -> dict[str, object]:
    """Resultado stub uniforme: honesto sobre que no hay backend real."""
    return {
        "status": "not_wired",
        "detail": "reminder backend pendiente",
        "action": action,
        "echo": arguments,
    }


class _SetReminderArgs(BaseModel):
    """Argumentos de ``reminder.set`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: ``when`` se manda como string ISO 8601
    (tipo ``IsoDatetime``, que rechaza epoch numerico); ``text`` mantiene la
    validacion strict.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    text: str
    when: IsoDatetime


class _ListRemindersArgs(BaseModel):
    """Argumentos de ``reminder.list`` (Pydantic v2 strict).

    Ventana opcional: sin argumentos lista todos los recordatorios activos.
    ``from_dt`` / ``to_dt`` aceptan strings ISO 8601 (ver ``_SetReminderArgs``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: IsoDatetime | None = None
    to_dt: IsoDatetime | None = None


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
