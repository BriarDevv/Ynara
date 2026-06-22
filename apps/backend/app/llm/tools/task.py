"""Tools del namespace ``task`` (stub playground + Fase D1 real, espejo de calendar).

DOS familias en este módulo, una por superficie (mismo patrón que ``calendar.py``):

1. STUBS sin efecto (``CreateTaskTool`` / ``ListTasksTool``): los del
   ``default_registry()``. Validan args y devuelven ``not_wired``. Los usa el
   **playground observado** (ADR-019 D2: invariante de no-efecto — el operador ve al
   agente decidir tools a CERO efecto). Cambiarlos rompería esa invariante (y su test
   guardián).

2. TOOLS REALES stateful (``AgentCreateTaskTool`` / ``AgentListTasksTool``, Fase D1):
   reciben un ``TaskStore`` ligado a ``(session, user_id)`` y ESCRIBEN/LEEN ``tasks``
   de verdad. Espejan EXACTAMENTE el patrón de las calendar tools reales
   (``AgentCreateEventTool`` etc.): el store viaja por closure de constructor, el
   ``user_id`` NUNCA como argumento (``extra='forbid'`` lo impide). Las consume SOLO la
   **pasada asíncrona del agente** vía ``task_registry(store)``, no el default.

Ambas familias comparten ``name``/``namespace`` (``task.create_task`` /
``task.list_tasks``): el modelo ve el mismo contrato; lo que cambia es si la tool
tiene efecto, decidido por QUÉ registry se arma (default observado vs task real),
igual que calendar.*/memory.*.

Args reales que espejan ``TaskCreate`` (``app/schemas/task.py``): ``title`` (+
``scheduled_at`` / ``duration_min`` opcionales). NO hay invariante entre campos (a
diferencia de Agenda).

El JSON Schema OpenAI de cada tool se deriva del propio modelo Pydantic
(``tool_schema``), así hay una sola fuente de verdad para validación y para lo que ve
el modelo. Los errores de validación vuelven como dict estructurado (``tool_error``),
nunca como excepción.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.tools.base import (
    AGENT_LIST_RESULT_LIMIT,
    IsoDatetime,
    first_validation_error,
    not_wired_result,
    tool_error,
    tool_schema,
)
from app.schemas.task import TaskCreate
from app.tasks.store import TaskStore

if TYPE_CHECKING:
    # Import perezoso en runtime (ver ``task_registry``): ``registry.py`` importa ESTE
    # módulo para los stubs del ``default_registry()``, así que importar
    # ``ToolRegistry`` a nivel de módulo cerraría un ciclo de import. La anotación de
    # tipo se resuelve solo en type-checking (no en runtime).
    from app.llm.tools.registry import ToolRegistry

_NAMESPACE = "task"
_DETAIL = "task backend pendiente"


class _CreateTaskArgs(BaseModel):
    """Argumentos de ``task.create_task`` (Pydantic v2 strict).

    Las tool calls llegan como JSON: ``due`` (opcional) se manda como string ISO 8601
    (tipo ``IsoDatetime``, que rechaza epoch numérico); el ``title`` mantiene la
    validación strict del modelo.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str
    due: IsoDatetime | None = None


class _ListTasksArgs(BaseModel):
    """Argumentos de ``task.list_tasks`` (Pydantic v2 strict).

    No recibe filtros (el stub lista todo); ``extra='forbid'`` rechaza cualquier arg.
    """

    model_config = ConfigDict(strict=True, extra="forbid")


class CreateTaskTool:
    """Crea una tarea/pendiente del usuario.

    TODO: cablear backend real. Por ahora valida los argumentos y devuelve un stub
    estructurado (invariante de no-efecto del playground observado, ADR-019).
    """

    name = f"{_NAMESPACE}.create_task"
    namespace = _NAMESPACE
    description = "Crea una tarea o pendiente del usuario."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_CreateTaskArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _CreateTaskArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)


class ListTasksTool:
    """Lista las tareas/pendientes del usuario.

    TODO: cablear backend real. Por ahora valida los argumentos y devuelve un stub
    estructurado (invariante de no-efecto del playground observado, ADR-019).
    """

    name = f"{_NAMESPACE}.list_tasks"
    namespace = _NAMESPACE
    description = "Lista las tareas o pendientes del usuario."

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_ListTasksArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _ListTasksArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))
        return not_wired_result(self.name, validated.model_dump(mode="json"), detail=_DETAIL)


# ===========================================================================
# Tools REALES con efecto (Fase D1) — escriben/leen tasks
# ===========================================================================
#
# Stateful: reciben un ``TaskStore`` ligado a ``(session, user_id)`` por closure de
# constructor (mismo patrón que ``AgentCreateEventTool(store)``). El ``user_id`` NUNCA
# viaja como argumento (el store ya lo tiene; ``extra='forbid'`` lo bloquea). Las
# consume SOLO ``task_registry(store)`` (la pasada async del agente), no
# ``default_registry()`` (que sigue con los stubs no-op del playground).


class _AgentCreateTaskArgs(BaseModel):
    """Argumentos REALES de ``task.create_task`` — espejan ``TaskCreate``.

    Mismo contrato de dominio que el alta de tareas (``app/schemas/task.py``):
    ``title`` no vacío + ``scheduled_at`` (ISO 8601, vía ``IsoDatetime`` que rechaza
    epoch numérico, opcional) + ``duration_min`` entero positivo (opcional).
    ``status`` NO se acepta (lo fija el store en ``pending``).

    ``extra='forbid'``: ``user_id`` (u otro campo) NO puede inyectarse por argumento
    (el store ya está ligado al ``user_id``; pasarlo permitiría crear tareas para otro
    usuario). Un extra desconocido es ``invalid_arguments``.

    ``strict=False`` (MISMO patrón que ``TaskCreate`` / ``ChatHttpRequest``, ver
    ``_WIRE_REQUEST_CONFIG`` en ``app/schemas/task.py``): las tool calls llegan como
    JSON. El epoch numérico en ``scheduled_at`` SIGUE rechazándose porque
    ``IsoDatetime`` usa un ``BeforeValidator`` que exige string ISO / datetime nativo
    (independiente de ``strict``). ``Field(gt=0)`` mantiene ``duration_min`` positivo.

    Cotas superiores LLM-fed (defensa en profundidad, lección de la review de Fase E):
    estos args los llena qwen, así que se ACOTAN para que un título de 50KB o una
    duración absurda no lleguen al store / la DB. ``TaskCreate`` (el dominio, contrato
    del front) NO lleva estos caps ("Pydantic gana"); el cap vive SOLO en la
    superficie del agente, que es la no confiable.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200)]
    scheduled_at: IsoDatetime | None = None
    # 43200 = un mes en minutos (30 días * 24h * 60min): cota razonable para un único
    # bloque de tarea; sigue ``gt=0`` (entero positivo, mismo piso que ``TaskCreate``).
    duration_min: Annotated[int, Field(gt=0, le=43200)] | None = None


class _AgentListTasksArgs(BaseModel):
    """Argumentos REALES de ``task.list_tasks`` (lista todas las tareas del usuario).

    No recibe filtros (el dashboard "Hoy" muestra todas); ``extra='forbid'`` rechaza
    cualquier arg inyectado (incluido ``user_id``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")


class AgentCreateTaskTool:
    """Crea una tarea REAL en ``tasks`` (Fase D1).

    La pasada asíncrona del agente (qwen por detrás de la conversación) llama esta
    tool para anotar los pendientes conversados. Escribe vía ``TaskStore`` (ligado al
    ``user_id`` real): aislamiento estructural + idempotencia (un retry de Celery no
    duplica la tarea; ver ``TaskStore.create_task``).

    El resultado es un dict serializable (``id`` + campos de la tarea), NO el ORM: el
    modelo / el caller ven la tarea creada sin metadata interna (``user_id`` /
    timestamps no se filtran, mismo contrato que ``TaskOut``).
    """

    name = f"{_NAMESPACE}.create_task"
    namespace = _NAMESPACE
    description = "Crea una tarea o pendiente del usuario."

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentCreateTaskArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AgentCreateTaskArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Construir el ``TaskCreate`` de dominio desde los args validados. Reusa el
        # schema canónico (un solo contrato): el store escribe lo mismo que el CRUD HTTP.
        payload = TaskCreate(
            title=validated.title,
            scheduled_at=validated.scheduled_at,
            duration_min=validated.duration_min,
        )
        return await self._store.create_task(payload)


class AgentListTasksTool:
    """Lista las tareas REALES del usuario (Fase D1).

    Read-only sobre ``tasks`` vía ``TaskStore`` (ligado al ``user_id`` real). Devuelve
    ``{"tasks": [...]}`` con las tareas serializadas (sin metadata interna), para que
    el agente sepa qué pendientes ya existen antes de crear (evita duplicar).
    """

    name = f"{_NAMESPACE}.list_tasks"
    namespace = _NAMESPACE
    description = "Lista las tareas o pendientes del usuario."

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentListTasksArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            _AgentListTasksArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Cap acotado (``AGENT_LIST_RESULT_LIMIT``): el resultado se inyecta en el context
        # del LLM, así que no se vuelcan miles de tareas en un solo turno.
        tasks = await self._store.list_tasks(limit=AGENT_LIST_RESULT_LIMIT)
        return {"tasks": tasks}


def task_registry(store: TaskStore) -> ToolRegistry:
    """Registry con las 2 task tools REALES ligadas a ``store`` (Fase D1).

    Espejo de ``calendar_registry(store)`` / ``memory_registry(store)``: NO toca
    ``default_registry()`` (que sigue con los stubs no-op del playground observado). Se
    construye aparte y se combina para la pasada asíncrona del agente cuando el modo
    habilita ``task`` en ``tools_enabled``.

    ``ToolRegistry`` se importa acá adentro (no a nivel de módulo): ``registry.py``
    importa ESTE módulo para los stubs del ``default_registry()``, así que un import
    top-level cerraría un ciclo. Cuando se llama a ``task_registry`` el ciclo ya está
    resuelto (ambos módulos cargados).
    """
    from app.llm.tools.registry import ToolRegistry

    return ToolRegistry(
        [
            AgentCreateTaskTool(store),
            AgentListTasksTool(store),
        ]
    )
