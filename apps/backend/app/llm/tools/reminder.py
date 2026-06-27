"""Tools del namespace ``reminder`` (stub playground + real, espejo de calendar/task).

DOS familias en este módulo, una por superficie (mismo patrón que ``calendar.py`` /
``task.py``):

1. STUBS sin efecto (``SetReminderTool`` / ``ListRemindersTool``): los del
   ``default_registry()``. Validan args y devuelven ``not_wired``. Los usa el
   **playground observado** (ADR-019 D2: invariante de no-efecto). Se mantienen tal cual:
   cambiarlos rompería esa invariante (y su test guardián).

2. TOOLS REALES stateful (``AgentSetReminderTool`` / ``AgentListRemindersTool``): reciben
   un ``ReminderStore`` ligado a ``(session, user_id)`` y ESCRIBEN/LEEN ``reminders`` de
   verdad. Espejan EXACTAMENTE el patrón de ``AgentCreateEventTool`` / ``AgentCreateTaskTool``:
   el store viaja por closure de constructor, el ``user_id`` NUNCA como argumento
   (``extra='forbid'`` lo impide). Las consume el chat de producción vía
   ``build_chat_tool_registry`` (a través de ``_AGENT_TOOL_BUILDERS``) y la pasada async
   del agente vía ``reminder_registry(store)``.

Ambas familias comparten ``name``/``namespace`` (``reminder.set`` / ``reminder.list``):
el modelo ve el mismo contrato; lo que cambia es si la tool tiene efecto, decidido por
QUÉ registry se arma.

Naming unificado en singular ``reminder`` (alineado con ``calendar``/``task`` y
``docs/TOOLS.md``): el namespace de habilitación por modo, el prefijo de los ``name`` y
este módulo son todos singulares.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from app.llm.tools.base import (
    AGENT_LIST_RESULT_LIMIT,
    IsoDatetime,
    first_validation_error,
    not_wired_result,
    tool_error,
    tool_schema,
)
from app.schemas.reminder import ReminderCreate

if TYPE_CHECKING:
    # Import perezoso en runtime (ver ``reminder_registry``): ``registry.py`` importa ESTE
    # módulo para los stubs del ``default_registry()``, así que importar ``ToolRegistry`` a
    # nivel de módulo cerraría un ciclo de import. La anotación de tipo se resuelve solo en
    # type-checking (no en runtime).
    from app.llm.tools.registry import ToolRegistry
    from app.services.reminders import ReminderStore

_NAMESPACE = "reminder"
_DETAIL = "reminder backend pendiente"


class _SetReminderArgs(BaseModel):
    """Argumentos de ``reminder.set`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: ``when`` se manda como string ISO 8601 (tipo
    ``IsoDatetime``, que rechaza epoch numerico); ``text`` mantiene la validacion strict.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    text: str
    when: IsoDatetime


class _ListRemindersArgs(BaseModel):
    """Argumentos de ``reminder.list`` (Pydantic v2 strict).

    Ventana opcional: sin argumentos lista todos los recordatorios activos. ``from_dt`` /
    ``to_dt`` aceptan strings ISO 8601 (ver ``_SetReminderArgs``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: IsoDatetime | None = None
    to_dt: IsoDatetime | None = None


class SetReminderTool:
    """Crea un recordatorio.

    STUB del playground observado (ADR-019): valida los argumentos y devuelve un stub
    estructurado. La tool REAL (con efecto) es ``AgentSetReminderTool``.
    """

    name = "reminder.set"
    namespace = _NAMESPACE
    description = "Crea un recordatorio para una fecha y hora."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_SetReminderArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _SetReminderArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)


class ListRemindersTool:
    """Lista los recordatorios del usuario.

    STUB del playground observado (ADR-019): valida los argumentos y devuelve un stub
    estructurado. La tool REAL (con efecto) es ``AgentListRemindersTool``.
    """

    name = "reminder.list"
    namespace = _NAMESPACE
    description = "Lista los recordatorios del usuario."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_ListRemindersArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _ListRemindersArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)


# ===========================================================================
# Tools REALES con efecto — escriben/leen reminders
# ===========================================================================
#
# Stateful: reciben un ``ReminderStore`` ligado a ``(session, user_id)`` por closure de
# constructor (mismo patrón que ``AgentCreateEventTool(store)``). El ``user_id`` NUNCA
# viaja como argumento (``extra='forbid'`` lo bloquea). Las consume ``reminder_registry``.


class _AgentSetReminderArgs(BaseModel):
    """Argumentos REALES de ``reminder.set``.

    Mismo contrato de la tool (``{text, when}``) que el stub, pero con cotas LLM-fed
    (defensa en profundidad, igual que calendar/task): ``text`` no vacío y ≤ 200, ``when``
    ISO 8601 (vía ``IsoDatetime`` que rechaza epoch numérico).

    ``strict=False`` (MISMO patrón que ``AgentCreateTaskArgs`` / ``ReminderCreate``): las
    tool calls llegan como JSON. El epoch numérico en ``when`` SIGUE rechazándose porque
    ``IsoDatetime`` usa un ``BeforeValidator`` (independiente de ``strict``).
    ``extra='forbid'``: ``user_id`` (u otro campo) NO puede inyectarse por argumento.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=200)]
    when: IsoDatetime


class _AgentListRemindersArgs(BaseModel):
    """Argumentos REALES de ``reminder.list`` (ventana OPCIONAL ``[from_dt, to_dt)``).

    La ventana es opcional: sin argumentos lista TODOS los recordatorios activos del
    usuario (``list_all``); con ventana, solo los que vencen en ``[from_dt, to_dt)``
    (``list_window``). Reglas (estos args los llena el LLM, así que se validan acá en vez
    de delegar al store una consulta sin sentido):

    - Si NINGUNO viene → válido (lista todos).
    - Si UNO viene, el OTRO también debe venir (una ventana parcial no tiene sentido).
    - Con ambos, la ventana debe ser no vacía: ``from_dt < to_dt``.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: IsoDatetime | None = None
    to_dt: IsoDatetime | None = None

    @model_validator(mode="after")
    def _check_window(self) -> _AgentListRemindersArgs:
        # ``PydanticCustomError`` (no ``ValueError`` pelado): el ``execute`` atrapa el
        # ``ValidationError`` y lo pasa por ``first_validation_error`` (que solo usa
        # ``loc``/``type``, nunca el valor — regla #4). Mismo patrón que el de calendar.
        if (self.from_dt is None) != (self.to_dt is None):
            raise PydanticCustomError(
                "incomplete_window",
                "from_dt y to_dt deben venir juntos (o ninguno).",
            )
        if self.from_dt is not None and self.to_dt is not None and self.from_dt >= self.to_dt:
            raise PydanticCustomError(
                "from_dt_after_to_dt",
                "from_dt debe ser anterior a to_dt.",
            )
        return self


class AgentSetReminderTool:
    """Crea un recordatorio REAL en ``reminders``.

    Escribe vía ``ReminderStore`` (ligado al ``user_id`` real): aislamiento estructural +
    idempotencia (un retry no duplica el aviso; ver ``ReminderStore.create_reminder``). El
    resultado es un dict serializable (``id`` + campos del recordatorio), NO el ORM.
    """

    name = "reminder.set"
    namespace = _NAMESPACE
    description = "Crea un recordatorio para una fecha y hora."

    def __init__(self, store: ReminderStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentSetReminderArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AgentSetReminderArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # ``when`` (contrato de la tool) mapea a ``remind_at`` (columna). Reusa el schema
        # de dominio ``ReminderCreate`` (un solo contrato): el store escribe lo mismo que
        # el CRUD HTTP.
        payload = ReminderCreate(text=validated.text, remind_at=validated.when)
        return await self._store.create_reminder(payload)


class AgentListRemindersTool:
    """Lista recordatorios REALES del usuario (todos los activos, o en una ventana).

    Read-only sobre ``reminders`` vía ``ReminderStore`` (ligado al ``user_id`` real).
    Devuelve ``{"reminders": [...]}`` (serializados, sin metadata interna). La ventana
    ``[from_dt, to_dt)`` es OPCIONAL: sin ella lista los activos del usuario.
    """

    name = "reminder.list"
    namespace = _NAMESPACE
    description = (
        "Lista los recordatorios del usuario. Sin argumentos devuelve todos; con la "
        "ventana opcional from_dt/to_dt (ISO 8601, ambos o ninguno) solo los pendientes "
        "que vencen en ese rango."
    )

    def __init__(self, store: ReminderStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentListRemindersArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AgentListRemindersArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Cap acotado (``AGENT_LIST_RESULT_LIMIT``) en ambas ramas: el resultado se inyecta
        # en el context del LLM, así que nunca se vuelca la cola completa del usuario. Sin
        # ventana → todos los activos (``list_all``); con ventana → solo el rango.
        if validated.from_dt is None:
            reminders = await self._store.list_all(limit=AGENT_LIST_RESULT_LIMIT, offset=0)
        else:
            reminders = await self._store.list_window(
                validated.from_dt, validated.to_dt, limit=AGENT_LIST_RESULT_LIMIT
            )
        return {"reminders": reminders}


def reminder_registry(store: ReminderStore) -> ToolRegistry:
    """Registry con las 2 reminder tools REALES ligadas a ``store``.

    Espejo de ``calendar_registry(store)`` / ``task_registry(store)``: NO toca
    ``default_registry()`` (que sigue con los stubs no-op del playground observado). Lo
    consumen el chat de producción (vía ``_AGENT_TOOL_BUILDERS``) y la pasada async del
    agente.

    ``ToolRegistry`` se importa acá adentro (no a nivel de módulo): ``registry.py`` importa
    ESTE módulo para los stubs del ``default_registry()``, así que un import top-level
    cerraría un ciclo. Cuando se llama a ``reminder_registry`` el ciclo ya está resuelto.
    """
    from app.llm.tools.registry import ToolRegistry

    return ToolRegistry(
        [
            AgentSetReminderTool(store),
            AgentListRemindersTool(store),
        ]
    )
