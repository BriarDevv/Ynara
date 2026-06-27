"""Tools del namespace ``calendar`` (M6 stubs + Fase E real, ADR-021).

DOS familias en este módulo, una por superficie:

1. STUBS sin efecto (``CreateEventTool`` / ``ListEventsTool``): los del
   ``default_registry()`` (M6). Validan args y devuelven ``not_wired``. Los usa
   el **playground observado** (ADR-019 D2: invariante de no-efecto — el operador
   ve al agente decidir tools a CERO efecto). Se quedan tal cual: cambiarlos
   rompería esa invariante (y su test guardián).

2. TOOLS REALES stateful (``AgentCreateEventTool`` / ``AgentListEventsTool``,
   Fase E ADR-021): reciben un ``CalendarEventStore`` ligado a ``(session,
   user_id)`` y ESCRIBEN/LEEN ``calendar_events`` de verdad. Espejan EXACTAMENTE
   el patrón de las memory tools reales (``MemoryUpdateTool`` etc.): el store
   viaja por closure de constructor, el ``user_id`` NUNCA como argumento (igual
   que la memoria; ``extra='forbid'`` lo impide). Las consume SOLO la **pasada
   asíncrona del agente** vía ``calendar_registry(store)``, no el default.

Ambas familias comparten ``name``/``namespace`` (``calendar.create_event`` /
``calendar.list_events``): el modelo ve el mismo contrato; lo que cambia es si la
tool tiene efecto, decidido por QUÉ registry se arma (default observado vs
calendar real), igual que memory.* (stub en default, real en memory_registry).

Args reales que espejan ``EventCreate`` (``app/schemas/calendar_event.py``):
``title`` / ``start_at`` / ``duration_min`` (+ ``mode`` / ``location`` /
``time_zone`` / ``recurrence`` opcionales). La invariante ADR-023
(``recurrence`` ⇒ ``time_zone``) se reusa del schema de dominio (un solo lugar).

El JSON Schema OpenAI de cada tool se deriva del propio modelo Pydantic
(``tool_schema``), asi hay una sola fuente de verdad para validacion y para
lo que ve el modelo. Los errores de validacion vuelven como dict estructurado
(``tool_error``), nunca como excepcion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.core.timezones import validate_iana_tz
from app.enums import Mode
from app.llm.tools.base import (
    AGENT_LIST_RESULT_LIMIT,
    IsoDatetime,
    first_validation_error,
    not_wired_result,
    tool_error,
    tool_schema,
)
from app.schemas.calendar_event import EventCreate, _validate_recurrence_needs_time_zone
from app.services.calendar import CalendarEventStore

if TYPE_CHECKING:
    # Import perezoso en runtime (ver ``calendar_registry``): ``registry.py`` importa
    # ESTE módulo para los stubs del ``default_registry()``, así que importar
    # ``ToolRegistry`` a nivel de módulo cerraría un ciclo de import. La anotación de
    # tipo se resuelve solo en type-checking (no en runtime).
    from app.llm.tools.registry import ToolRegistry

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


# ===========================================================================
# Tools REALES con efecto (Fase E, ADR-021) — escriben/leen calendar_events
# ===========================================================================
#
# Stateful: reciben un ``CalendarEventStore`` ligado a ``(session, user_id)`` por
# closure de constructor (mismo patrón que ``MemoryUpdateTool(store)``). El
# ``user_id`` NUNCA viaja como argumento (el store ya lo tiene; ``extra='forbid'``
# lo bloquea). Las consume SOLO ``calendar_registry(store)`` (la pasada async del
# agente), no ``default_registry()`` (que sigue con los stubs no-op del playground).


class _AgentCreateEventArgs(BaseModel):
    """Argumentos REALES de ``calendar.create_event`` — espejan ``EventCreate``.

    Mismo contrato de dominio que ``POST /v1/events`` (``app/schemas/calendar_event.py``):
    ``title`` no vacío + ``start_at`` (ISO 8601, vía ``IsoDatetime`` que rechaza
    epoch numérico) + ``duration_min`` entero positivo, con ``mode`` / ``location`` /
    ``time_zone`` / ``recurrence`` opcionales. ``status`` NO se acepta (lo fija el
    store en ``confirmed``). La invariante ADR-023 (``recurrence`` ⇒ ``time_zone``)
    se valida con la MISMA función del schema de dominio (un solo lugar).

    ``extra='forbid'``: ``user_id`` (u otro campo) NO puede inyectarse por argumento
    (el store ya está ligado al ``user_id``; pasarlo permitiría agendar para otro
    usuario). Un extra desconocido es ``invalid_arguments``.

    ``strict=False`` (MISMO patrón que ``EventCreate`` / ``ChatHttpRequest``, ver
    ``_WIRE_REQUEST_CONFIG`` en ``app/schemas/calendar_event.py``): las tool calls
    llegan como JSON, así que ``mode`` viaja como string (``"productividad"``) y debe
    coercionarse a ``Mode``. Con ``strict=True`` un string no es instancia de ``Mode``
    y fallaría. El epoch numérico en ``start_at`` SIGUE rechazándose porque
    ``IsoDatetime`` usa un ``BeforeValidator`` que exige string ISO / datetime nativo
    (independiente de ``strict``). ``Field(gt=0)`` mantiene ``duration_min`` positivo.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    # Cotas superiores LLM-fed (defensa en profundidad): estos args los llena qwen,
    # así que se ACOTAN para que un título de 50KB, una duración absurda o una lista de
    # recurrencia gigante no lleguen al store / la DB. ``EventCreate`` (el dominio de
    # #402) NO lleva estos caps (su contrato es el del front, "Pydantic gana"); el cap
    # vive SOLO en la superficie del agente, que es la no confiable.
    title: Annotated[str, Field(min_length=1, max_length=200)]
    start_at: IsoDatetime
    # 43200 = un mes en minutos (30 días * 24h * 60min): cota razonable para un único
    # bloque de evento; sigue ``gt=0`` (entero positivo, mismo piso que ``EventCreate``).
    duration_min: Annotated[int, Field(gt=0, le=43200)]
    mode: Mode | None = None
    # Eventos de día completo (cumpleaños / feriados): el agente puede agendarlos.
    # Default ``False``, mismo piso que ``EventCreate.all_day``.
    all_day: bool = False
    location: Annotated[str, Field(max_length=500)] | None = None
    time_zone: Annotated[str, Field(max_length=64)] | None = None
    # Lista de reglas RRULE acotada: como máximo 50 ítems, cada uno ≤ 500 chars.
    recurrence: list[Annotated[str, Field(max_length=500)]] | None = Field(
        default=None, max_length=50
    )

    @field_validator("time_zone", mode="before")
    @classmethod
    def _check_time_zone_iana(cls, v: object) -> object:
        # Validación IANA vía ``validate_iana_tz`` (sede única en ``app/core/timezones.py``,
        # DRY con ``app/schemas/user.py``): un string que no es un identificador IANA real
        # (p.ej. "UTC+3" o cualquier string arbitrario) levanta ``ValueError``.
        # ``PydanticCustomError`` (no ``ValueError`` pelado): el ``execute`` atrapa el
        # ``ValidationError`` y lo pasa por ``first_validation_error`` (que solo usa
        # ``loc``/``type``, nunca el valor — regla #4). Mismo patrón que
        # ``_check_window_order`` en ``_AgentListEventsArgs``.
        if v is not None:
            try:
                validate_iana_tz(str(v))
            except ValueError:
                # ``from None`` (B904): corta el encadenamiento para que el traceback NO
                # arrastre el valor inválido del usuario (regla #4). El ctx del custom error
                # solo lleva loc/type, nunca el string original.
                raise PydanticCustomError(
                    "invalid_time_zone",
                    "time_zone debe ser un identificador IANA válido.",
                ) from None
        return v

    @model_validator(mode="after")
    def _check_recurrence_time_zone(self) -> _AgentCreateEventArgs:
        # Misma sede que ``EventCreate`` / el router de eventos: recurrencia no vacía
        # exige ``time_zone`` (ADR-023). Reusar la función evita duplicar la regla.
        _validate_recurrence_needs_time_zone(self.recurrence, self.time_zone)
        return self


class _AgentListEventsArgs(BaseModel):
    """Argumentos REALES de ``calendar.list_events`` (ventana ``[from_dt, to_dt)``).

    La ventana debe ser no vacía: ``from_dt < to_dt``. Como estos args los llena el
    LLM, una ventana invertida (o de ancho cero) se rechaza acá en vez de delegar al
    store una consulta sin sentido.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    from_dt: IsoDatetime
    to_dt: IsoDatetime

    @model_validator(mode="after")
    def _check_window_order(self) -> _AgentListEventsArgs:
        # ``PydanticCustomError`` (no ``ValueError`` pelado): el ``execute`` atrapa el
        # ``ValidationError`` y lo pasa por ``first_validation_error`` (que solo usa
        # ``loc``/``type``, nunca el valor — regla #4). Usar el custom error mantiene un
        # ``type`` estable y serializable (mismo patrón que ``_validate_recurrence_*``),
        # así no hay datos del usuario ni objetos no serializables en el ``ctx``.
        if self.from_dt >= self.to_dt:
            raise PydanticCustomError(
                "from_dt_after_to_dt",
                "from_dt debe ser anterior a to_dt.",
            )
        return self


class AgentCreateEventTool:
    """Agenda un evento REAL en ``calendar_events`` (Fase E, ADR-021).

    La pasada asíncrona del agente (qwen por detrás de la conversación) llama esta
    tool para agendar lo conversado. Escribe vía ``CalendarEventStore`` (ligado al
    ``user_id`` real): aislamiento estructural + idempotencia (un retry de Celery no
    duplica el evento; ver ``CalendarEventStore.create_event``).

    El resultado es un dict serializable (``id`` + campos del evento), NO el ORM:
    el modelo / el caller ven el evento creado sin metadata interna (``user_id`` /
    timestamps no se filtran, mismo contrato que ``CalendarEventOut``).
    """

    name = f"{_NAMESPACE}.create_event"
    namespace = _NAMESPACE
    description = "Agenda un evento en el calendario del usuario."

    def __init__(self, store: CalendarEventStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentCreateEventArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AgentCreateEventArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Construir el ``EventCreate`` de dominio desde los args validados. Reusa el
        # schema canónico (un solo contrato): el store escribe lo mismo que el CRUD HTTP.
        payload = EventCreate(
            title=validated.title,
            start_at=validated.start_at,
            duration_min=validated.duration_min,
            mode=validated.mode,
            all_day=validated.all_day,
            location=validated.location,
            time_zone=validated.time_zone,
            recurrence=validated.recurrence,
        )
        return await self._store.create_event(payload)


class AgentListEventsTool:
    """Lista eventos REALES del usuario en una ventana de tiempo (Fase E, ADR-021).

    Read-only sobre ``calendar_events`` vía ``CalendarEventStore`` (ligado al
    ``user_id`` real). Devuelve ``{"events": [...]}`` con los eventos serializados
    (sin metadata interna), para que el agente sepa qué ya está agendado antes de
    agendar (evita pisar / duplicar).
    """

    name = f"{_NAMESPACE}.list_events"
    namespace = _NAMESPACE
    description = "Lista eventos del calendario en una ventana de tiempo."

    def __init__(self, store: CalendarEventStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AgentListEventsArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AgentListEventsArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Cap acotado (``AGENT_LIST_RESULT_LIMIT``): el resultado se inyecta en el context
        # del LLM, así que no se vuelca una ventana de tiempo gigante completa.
        events = await self._store.list_events(
            validated.from_dt, validated.to_dt, limit=AGENT_LIST_RESULT_LIMIT
        )
        return {"events": events}


def calendar_registry(store: CalendarEventStore) -> ToolRegistry:
    """Registry con las 2 calendar tools REALES ligadas a ``store`` (Fase E, ADR-021).

    Espejo de ``memory_registry(store)``: NO toca ``default_registry()`` (que sigue
    con los stubs no-op del playground observado). Se construye aparte y se combina
    para la pasada asíncrona del agente cuando el modo habilita ``calendar`` en
    ``tools_enabled``.

    ``ToolRegistry`` se importa acá adentro (no a nivel de módulo): ``registry.py``
    importa ESTE módulo para los stubs del ``default_registry()``, así que un import
    top-level cerraría un ciclo. Cuando se llama a ``calendar_registry`` el ciclo ya
    está resuelto (ambos módulos cargados).
    """
    from app.llm.tools.registry import ToolRegistry

    return ToolRegistry(
        [
            AgentCreateEventTool(store),
            AgentListEventsTool(store),
        ]
    )
