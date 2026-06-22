"""Construcción de registries de tools de agente (hogar canónico, capa ``llm.tools``).

Este módulo es la FUENTE ÚNICA del mapping ``namespace -> builder`` de las tools de
agente con efecto real (``calendar`` / ``task``) y de las dos formas de armar un
``ToolRegistry`` a partir de él:

1. ``_build_agent_registry``: combina SOLO las tools reales de los namespaces
   habilitados. La usa la **pasada asíncrona** del agente
   (``app/workflows/agent_pass.py``), que históricamente vivía acá. Sin cambios de
   comportamiento: se movió desde ``agent_pass`` para que el chat de producción
   (``app/llm/context.py``) también pueda construir las tools reales sin importar el
   módulo de workflows (capa equivocada + riesgo de ciclo Celery↔router).

2. ``build_chat_tool_registry``: lo que consume el **tool-loop SÍNCRONO del chat de
   producción** (ADR-022). Es ``_build_agent_registry`` MÁS los stubs de ``reminder``
   cuando el modo los habilita. La diferencia con la pasada async es deliberada y se
   explica abajo.

Gating por modo (``tools_enabled``)
-----------------------------------
TODO el armado está gateado por ``tools_enabled`` del modo activo (config-driven,
``ynara.config.json``): una tool solo se construye/expone si su namespace está en esa
lista. Es el MISMO gate que usa la pasada async (ADR-021) y el que filtra las specs
hacia el modelo (``specs_for(enabled)``). El efecto neto: ``calendar``/``task`` reales
solo existen en ``productividad`` (el único modo que los habilita hoy); los modos
gemma (``tools_enabled=[]``) obtienen un registry vacío.

Por qué ``reminder`` SIGUE siendo stub
---------------------------------------
``reminder`` está en ``tools_enabled`` de ``productividad``, pero NO tiene backend
real todavía (no existe tabla ``reminders`` ni scheduler): sus únicas
implementaciones son los stubs ``SetReminderTool`` / ``ListRemindersTool`` que validan
args y devuelven ``not_wired``. Por eso ``build_chat_tool_registry`` registra esos
stubs cuando el modo habilita ``reminder``: así el modelo sigue VIENDO la tool (el
contrato no cambia) pero llamarla no tiene efecto, igual que antes de ADR-022. Cuando
``reminder`` tenga store real, se agrega su builder a ``_AGENT_TOOL_BUILDERS`` y deja
de tratarse como stub (sin tocar el resto del flujo).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# Imports perezosos en runtime (ver los wrappers de abajo). Todos los símbolos del layer de
# dominio (``CalendarEventStore`` / ``TaskStore``) y del propio ``llm.tools``
# (``ToolRegistry``) se importan DENTRO de las funciones, no a nivel de módulo:
#
# - ``ToolRegistry``: ``registry.py`` importa ``calendar.py`` / ``task.py`` para los stubs
#   del ``default_registry()``, así que un import top-level de ``ToolRegistry`` acá arriesga
#   un ciclo ``registry.py`` → calendar/task → (eventualmente) este módulo. Se anota perezoso
#   vía ``TYPE_CHECKING`` (la anotación se resuelve solo en type-checking).
# - ``CalendarEventStore`` / ``TaskStore``: este módulo se carga en startup (``context.py`` lo
#   importa a nivel de módulo). Dejar los imports de los stores adentro de los wrappers los
#   resuelve LAZY (recién al construir el registry), de forma consistente con el patrón de
#   ``ToolRegistry`` y a prueba de futuro: si algún store empezara a importar del layer
#   ``llm`` se cerraría un ciclo silencioso que con el import top-level no se detectaría. Hoy
#   NO hay ciclo (calendar/task NO importan este módulo), pero el patrón lazy lo mantiene
#   blindado. Como ya no se anotan a nivel de módulo, no necesitan entrada en ``TYPE_CHECKING``.
if TYPE_CHECKING:
    from app.llm.tools.registry import ToolRegistry

# Mapping ``namespace -> builder(session, user_id) -> ToolRegistry`` de las tools de
# agente accionables (con efecto real). Las dos funciones de abajo construyen SOLO los
# registries de los namespaces que el modo habilita (la intersección con
# ``mode_cfg.tools_enabled``) y los combinan en uno. Diseño escalable: agregar una tool
# de agente nueva (con backend real) es agregar una entrada acá + el namespace al
# ``tools_enabled`` del modo en ``ynara.config.json``. El orden del dict define el orden
# de las specs en el prompt (determinista).
#
# ``ToolRegistry`` se anota perezosamente vía import diferido en cada función (mismo
# patrón que ``calendar.py`` / ``task.py``): ``registry.py`` importa esos módulos para
# los stubs del ``default_registry()``, así que un import top-level de ``ToolRegistry``
# acá arriesga un ciclo. Las builders del mapping devuelven ``ToolRegistry`` (lo
# construyen ``calendar_registry`` / ``task_registry`` con su propio import diferido).
_AGENT_TOOL_BUILDERS: dict[str, Callable[[AsyncSession, UUID], ToolRegistry]] = {
    "calendar": lambda session, user_id: _calendar_registry(session, user_id),
    "task": lambda session, user_id: _task_registry(session, user_id),
}


def _calendar_registry(session: AsyncSession, user_id: UUID) -> ToolRegistry:
    """Construye el calendar registry difiriendo los imports del store + registry (evita ciclo).

    ``CalendarEventStore`` y ``calendar_registry`` se importan acá adentro (no a nivel de
    módulo): así el store de dominio se resuelve LAZY (recién al armar el registry, no en
    startup) y a prueba de ciclos futuros (ver el bloque ``TYPE_CHECKING``).
    """
    from app.calendar.store import CalendarEventStore
    from app.llm.tools.calendar import calendar_registry

    return calendar_registry(CalendarEventStore(session, user_id))


def _task_registry(session: AsyncSession, user_id: UUID) -> ToolRegistry:
    """Construye el task registry difiriendo los imports del store + registry (evita ciclo).

    ``TaskStore`` y ``task_registry`` se importan acá adentro (no a nivel de módulo): así el
    store de dominio se resuelve LAZY (recién al armar el registry, no en startup) y a prueba
    de ciclos futuros (ver el bloque ``TYPE_CHECKING``).
    """
    from app.llm.tools.task import task_registry
    from app.tasks.store import TaskStore

    return task_registry(TaskStore(session, user_id))


def _build_agent_registry(
    session: AsyncSession, user_id: UUID, enabled_namespaces: list[str]
) -> ToolRegistry:
    """Combina las tools de agente de los namespaces habilitados en UN ``ToolRegistry``.

    Opción A del diseño multi-tool (ADR-021): construye SOLO los registries de
    ``_AGENT_TOOL_BUILDERS`` cuyo namespace está en ``enabled_namespaces`` (la
    intersección con ``mode_cfg.tools_enabled``) y los fusiona en uno solo registrando
    todas las tools (``calendar.*`` y ``task.*`` no colisionan). ``registries`` del
    loop sigue siendo ``(reg, None)`` (no se toca ``run_tool_loop``).

    El orden de iteración es el de ``_AGENT_TOOL_BUILDERS`` (determinista), filtrado por
    los habilitados, así el prompt es reproducible. Comportamiento idéntico al que tenía
    cuando vivía en ``agent_pass``: la pasada async lo sigue usando tal cual.
    """
    from app.llm.tools.registry import ToolRegistry

    combined = ToolRegistry()
    enabled = set(enabled_namespaces)
    for namespace, builder in _AGENT_TOOL_BUILDERS.items():
        if namespace in enabled:
            for tool in builder(session, user_id).tools():
                combined.register(tool)
    return combined


def build_chat_tool_registry(
    session: AsyncSession, user_id: UUID, tools_enabled: list[str]
) -> ToolRegistry:
    """Registry para el tool-loop SÍNCRONO del chat de producción (ADR-022).

    A diferencia del playground (``default_registry()``, cero efecto, ADR-019) y de la
    pasada async (solo tools reales, ADR-021), el chat de producción necesita un único
    registry que:

    - traiga las tools de agente REALES (``calendar`` / ``task``) de los namespaces que
      el modo habilita en ``tools_enabled`` — vía ``_build_agent_registry``, así
      ``calendar.create_event`` ESCRIBE de verdad en el turno (atómico con el commit del
      turno; las semánticas de commit las da ``ChatService.run_turn``), y
    - registre ADEMÁS los stubs ``not_wired`` de ``reminder`` cuando el modo lo habilita,
      porque ``reminder`` no tiene backend real todavía (ver el docstring del módulo): el
      modelo sigue viendo la tool pero llamarla no tiene efecto.

    Gating estricto por modo: un namespace que NO esté en ``tools_enabled`` no aporta
    ninguna tool. Para los modos gemma (``tools_enabled=[]``) el registry queda vacío;
    para ``memoria`` (``tools_enabled=[memory]``) tampoco hay calendar/task/reminder (el
    namespace ``memory`` lo maneja ``MemoryContext`` aparte, vía ``memory_registry``).

    Los stubs de ``reminder`` se importan diferido (mismo motivo de ciclo que arriba).
    """
    from app.llm.tools.reminder import ListRemindersTool, SetReminderTool

    # Base: las tools de agente REALES de los namespaces habilitados (calendar/task).
    # ``_build_agent_registry`` ya devuelve un ``ToolRegistry`` (con su import diferido).
    registry = _build_agent_registry(session, user_id, tools_enabled)

    # ``reminder`` habilitado pero sin backend real -> se agregan los stubs not_wired,
    # así el contrato hacia el modelo no cambia mientras el backend no exista.
    if "reminder" in tools_enabled:
        registry.register(SetReminderTool())
        registry.register(ListRemindersTool())

    return registry
