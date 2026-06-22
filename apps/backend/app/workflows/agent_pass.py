"""Pasada ASÍNCRONA del agente qwen sobre el turno conversado (Fase E, ADR-021;
MULTI-TOOL desde Fase D1).

"qwen por detrás de gemma": el usuario conversa con el modelo conversacional
(respuesta rápida en streaming); ESTA task corre por detrás, async, y a partir de
lo conversado **acciona las tools del agente** que el modo habilita: hoy **agenda
eventos** (``calendar``) y **crea tareas/pendientes** (``task``); en fases futuras,
más namespaces. Espejo EXACTO de ``consolidate_turn``
(``app/workflows/consolidation.py``):

1. Solo encolada cuando el modo habilita ALGUNA tool de agente accionable
   (``calendar`` o ``task``) en ``tools_enabled``. El caller
   (``ChatService._enqueue_agent_pass``) ya filtra; esta task RE-CHEQUEA el gate de
   forma defensiva (un payload viejo / cambio de config entre enqueue y run no debe
   accionar en un modo que ya no habilita esas tools).
2. NUNCA en el path de respuesta: ``ChatService.run_turn`` encola con ``.delay()``
   DESPUÉS del commit; el efecto (escribir ``calendar_events`` / ``tasks``) ocurre
   acá, en el worker Celery, async.
3. Responsabilidad ÚNICA: tools/acciones (calendar + task). NO toca memoria — eso es
   ``consolidate_turn``, una task separada gateada por ``writes_memory`` (ADR-021
   D3: memoria y tools se operan/escalan/reintentan por separado).
4. Serialización 100% JSON: la firma es solo strings/primitivos. El worker
   RECONSTRUYE sus deps in-process desde ``get_settings()``. El engine de DB usa
   ``NullPool`` obligatorio (igual que la consolidación, decisión #4).
5. IDEMPOTENCIA (ADR-021): la pasada NO debe duplicar acciones ante un reintento de
   Celery. La estrategia es **idempotencia de la tool**: cada tool real deduplica por
   su tupla natural (``calendar.create_event`` por ``(user_id, title, start_at,
   duration_min)``; ``task.create_task`` por ``(user_id, title, scheduled_at)``), así
   re-correr el mismo turno → la misma tool call → no crea la acción dos veces. Sumado
   al at-most-once del broker (``task_acks_late=False``), un pendiente/evento
   conversado se acciona una sola vez. ``MAX_TOOL_ITERATIONS`` (5) acota el loop.
6. Ningún dato de usuario a logs (regla #4): el turno queda on-prem en
   Redis/worker; solo se loguea el conteo de acciones y el tipo de excepción.

DISEÑO MULTI-TOOL (Opción A, escalable): en vez de hardcodear UN registry de
calendar, ``_AGENT_TOOL_BUILDERS`` mapea ``namespace -> builder(session, user_id) ->
ToolRegistry``. La pasada construye SOLO los registries de los namespaces que el modo
habilita (la intersección de ``_AGENT_TOOL_BUILDERS`` con ``mode_cfg.tools_enabled``)
y los combina en UN ``ToolRegistry`` (las tools no colisionan: ``calendar.*`` vs
``task.*``). ``specs_for(enabled)`` filtra por namespace → si un modo tiene
``calendar`` pero no ``task``, las task specs no se mandan al modelo. Agregar una tool
de agente nueva es agregar una entrada al mapping + el namespace al ``tools_enabled``
del modo. El gate sigue siendo ``tools_enabled`` del modo (config-driven, ADR-021).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar.store import CalendarEventStore
from app.core.config import Settings, get_settings
from app.llm.clients.base import LLMClient
from app.llm.clients.factory import build_llm_client
from app.llm.config import load_llm_config
from app.llm.schemas import ChatMessage
from app.llm.tool_loop import run_tool_loop
from app.llm.tools.calendar import calendar_registry
from app.llm.tools.registry import ToolRegistry
from app.llm.tools.task import task_registry
from app.tasks.store import TaskStore
from app.workers.celery_app import celery_app
from app.workflows._engine import worker_session

logger = logging.getLogger(__name__)

# Mapping ``namespace -> builder(session, user_id) -> ToolRegistry`` de las tools de
# agente accionables (con efecto real). La pasada construye SOLO los registries de los
# namespaces que el modo habilita (la intersección con ``mode_cfg.tools_enabled``) y
# los combina en uno. Diseño escalable: agregar una tool de agente nueva es agregar
# una entrada acá + el namespace al ``tools_enabled`` del modo en ``ynara.config.json``.
# El orden del dict define el orden de las specs en el prompt (determinista).
_AGENT_TOOL_BUILDERS: dict[str, Callable[[AsyncSession, UUID], ToolRegistry]] = {
    "calendar": lambda session, user_id: calendar_registry(CalendarEventStore(session, user_id)),
    "task": lambda session, user_id: task_registry(TaskStore(session, user_id)),
}

# System prompt de la pasada del agente. NO es el prompt conversacional del modo
# (ese lo usa gemma para hablar): este instruye a qwen a OBSERVAR lo conversado y
# ACCIONAR las tools si corresponde, sin charlar. Estático (no depende del usuario).
# S105: NO es un secreto — es el system prompt del agente (el nombre contiene
# "SYSTEM" y dispara el falso positivo de hardcoded-password).
_AGENT_PASS_SYSTEM = (
    "Sos el agente de Ynara que trabaja por detrás de la conversación. "  # noqa: S105
    "Recibís un turno ya conversado (mensaje del usuario + respuesta del asistente). "
    "Tu tarea es ACCIONAR lo que se haya acordado o pedido usando las tools disponibles: "
    "si el turno implica un evento concreto (con fecha/hora), usá la tool "
    "calendar.create_event con título, start_at (ISO 8601 con huso) y duración en "
    "minutos. Si el turno implica una tarea o pendiente concreto, usá la tool "
    "task.create_task con título (y scheduled_at en ISO 8601 con huso si tiene horario). "
    "Si no hay nada para accionar, no llames ninguna tool y respondé vacío. "
    "No inventes acciones que no estén en lo conversado. No converses con el usuario: "
    "solo accionás las tools."
)

# Texto de fallback del tool loop. Esta pasada NO surfacea texto al usuario (el
# resultado son las acciones persistidas, ADR-021 D4), así que el fallback es
# irrelevante de cara al usuario; existe solo para satisfacer el contrato del loop.
_FALLBACK_TEXT = "(agente: sin acción)"


def _build_agent_llm(settings: Settings) -> LLMClient:
    """Construye el cliente LLM para la pasada del agente (qwen).

    Delega en la factory (``build_llm_client``), igual que la consolidación: respeta
    ``LLM_BACKEND`` (dev/test -> ``FakeLlmClient``; ``vllm``/prod -> cliente real
    contra Ollama/vLLM). El gate fake-vs-real vive en un solo lugar (la factory); la
    pasada no lo re-chequea.
    """
    return build_llm_client(settings, load_llm_config())


def _build_turn_message(user_msg: str, model_response: str) -> str:
    """Arma el ``user`` message del loop: el turno conversado, para que qwen lo lea.

    NO se loguea (es contenido del usuario, regla #4): solo viaja al LLM on-prem.
    """
    return f"Usuario: {user_msg}\nAsistente: {model_response}"


def _build_agent_registry(
    session: AsyncSession, user_id: UUID, enabled_namespaces: list[str]
) -> ToolRegistry:
    """Combina las tools de agente de los namespaces habilitados en UN ``ToolRegistry``.

    Opción A del diseño multi-tool: construye SOLO los registries de
    ``_AGENT_TOOL_BUILDERS`` cuyo namespace está en ``enabled_namespaces`` (la
    intersección con ``mode_cfg.tools_enabled``) y los fusiona en uno solo registrando
    todas las tools (``calendar.*`` y ``task.*`` no colisionan). ``registries`` del
    loop sigue siendo ``(reg, None)`` (no se toca ``run_tool_loop``).

    El orden de iteración es el de ``_AGENT_TOOL_BUILDERS`` (determinista), filtrado por
    los habilitados, así el prompt es reproducible.
    """
    combined = ToolRegistry()
    enabled = set(enabled_namespaces)
    for namespace, builder in _AGENT_TOOL_BUILDERS.items():
        if namespace in enabled:
            for tool in builder(session, user_id).tools():
                combined.register(tool)
    return combined


async def _run_agent_pass_in_db(
    *,
    session: AsyncSession,
    user_id: UUID,
    enabled_namespaces: list[str],
    served_name: str,
    user_msg: str,
    model_response: str,
    thinking: bool | None,
    llm_client: LLMClient,
) -> int:
    """Núcleo de la pasada sobre una ``session`` ya abierta. Retorna #acciones ejecutadas.

    Construye el registry COMBINADO de las tools de agente que el modo habilita
    (``enabled_namespaces``: intersección de ``_AGENT_TOOL_BUILDERS`` con
    ``tools_enabled``), arma ``messages = [system, turno]`` y corre ``run_tool_loop``
    con las specs de esos namespaces. Las tool calls que el modelo emita se ejecutan
    (creando eventos/tareas reales, idempotentes). NO commitea: el commit lo da el
    caller (``worker_session`` en prod, o el fixture en tests).
    """
    agent_reg = _build_agent_registry(session, user_id, enabled_namespaces)
    specs = agent_reg.specs_for(enabled_namespaces)

    messages = [
        ChatMessage(role="system", content=_AGENT_PASS_SYSTEM),
        ChatMessage(role="user", content=_build_turn_message(user_msg, model_response)),
    ]

    # registries = (agent_reg, None): el registry combinado tiene TODAS las tools de
    # agente habilitadas. El loop ejecuta cada tool call vía ese registry real.
    _text, actions, _finish_reason = await run_tool_loop(
        llm_client=llm_client,
        served_name=served_name,
        messages=messages,
        specs=specs,
        registries=(agent_reg, None),
        thinking=thinking,
        fallback_text=_FALLBACK_TEXT,
    )
    return len(actions)


async def _async_agent_pass(
    *,
    user_id: str,
    session_id: str,
    user_msg: str,
    model_response: str,
    mode: str,
    # Inyectables para tests (None => construir desde get_settings())
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    # session inyectable para tests de integración (evita crear engine nuevo)
    session: AsyncSession | None = None,
) -> int:
    """Núcleo async de la pasada del agente; retorna la cantidad de acciones ejecutadas.

    Gate (ADR-021 D2/D5, config-driven): se corre SOLO si el modo habilita ALGUNA tool
    de agente accionable (``calendar`` o ``task``, las claves de
    ``_AGENT_TOOL_BUILDERS``) en ``tools_enabled``. Si no, retorna 0 sin tocar nada (un
    modo sin esas tools no acciona). El gate se re-evalúa acá de forma defensiva: el
    caller ya filtra, pero un payload viejo / cambio de config no debe accionar en un
    modo que ya no habilita esas tools. Las tools que SÍ se mandan al modelo son la
    intersección del modo con ``_AGENT_TOOL_BUILDERS`` (un modo con ``calendar`` pero
    sin ``task`` no ve las task specs).

    Si ``session`` se inyecta (tests), se usa directamente y NO se crea engine ni se
    commitea (el fixture controla el ciclo de vida). Si es ``None`` (worker Celery en
    prod), se construye el engine con ``NullPool`` (decisión #4), se abre la sesión,
    se commitea y se dispone el engine.

    El ``served_name`` del modelo del modo (NUNCA la key interna) se resuelve de la
    config; ``thinking`` se fuerza ``True`` (el agente planifica tool calls — el rol
    de qwen es ``agent``, mismo criterio que el router).
    """
    cfg = settings or get_settings()
    runtime = load_llm_config()

    mode_cfg = runtime.modes.get(mode)
    # Gate: modo desconocido -> no-op. Si el modo existe, los namespaces accionables
    # son la intersección de los builders con su ``tools_enabled``; si esa intersección
    # es vacía (ninguna tool de agente habilitada), no-op (no se acciona).
    if mode_cfg is None:
        return 0
    enabled_namespaces = [ns for ns in _AGENT_TOOL_BUILDERS if ns in mode_cfg.tools_enabled]
    if not enabled_namespaces:
        return 0

    model_cfg = runtime.model_for_mode(mode)
    # El agente piensa para planificar tool calls (rol agent), igual que el router.
    thinking = model_cfg.role == "agent"

    uid = UUID(user_id)
    effective_llm = llm_client or _build_agent_llm(cfg)

    if session is not None:
        # Modo test: usar la sesión inyectada, sin engine ni commit (lo controla el fixture).
        return await _run_agent_pass_in_db(
            session=session,
            user_id=uid,
            enabled_namespaces=enabled_namespaces,
            served_name=model_cfg.served_name,
            user_msg=user_msg,
            model_response=model_response,
            thinking=thinking,
            llm_client=effective_llm,
        )

    # Modo producción: engine NullPool efímero; worker_session commitea al salir del
    # bloque y dispone el engine (decisión #4 centralizada en _engine.py).
    async with worker_session(cfg) as db_session:
        return await _run_agent_pass_in_db(
            session=db_session,
            user_id=uid,
            enabled_namespaces=enabled_namespaces,
            served_name=model_cfg.served_name,
            user_msg=user_msg,
            model_response=model_response,
            thinking=thinking,
            llm_client=effective_llm,
        )


@celery_app.task(bind=True, name="workflows.agent_turn_pass")
def agent_turn_pass(
    self,  # bind=True, self no se usa (sin retry manual; at-most-once + tool idempotente)
    *,
    user_id: str,
    session_id: str,
    user_msg: str,
    model_response: str,
    mode: str,
) -> None:
    """Task Celery: pasada async del agente que agenda lo conversado (Fase E, ADR-021).

    Firma 100% strings/primitivos (``task_serializer='json'``). NUNCA cruza el wire
    un ``AsyncSession``, un ``LLMClient``, un ``UUID`` ni un store.

    El cuerpo async se corre con ``asyncio.run`` (worker prefork de Celery). Todo el
    bloque se envuelve en ``try/except``: un fallo NO tumba el worker (loguea un
    mensaje SIN el contenido del usuario, regla #4: solo ``type(exc).__name__``).

    Args:
        user_id: UUID del usuario como string (JSON-safe).
        session_id: ``str(ChatSession.id)`` (id real de la sesión). Hoy la pasada de
            calendar no lo necesita como FK (los eventos se atan al ``user_id``); se
            propaga para trazabilidad y para fases futuras (reminders ligados a la
            sesión). NO se loguea su contenido (es un identificador, no PII).
        user_msg: Mensaje del usuario (on-prem, NO se loguea).
        model_response: Respuesta del modelo (on-prem, NO se loguea).
        mode: Modo activo de la sesión (gatea calendar via ``tools_enabled``).
    """
    try:
        actions = asyncio.run(
            _async_agent_pass(
                user_id=user_id,
                session_id=session_id,
                user_msg=user_msg,
                model_response=model_response,
                mode=mode,
            )
        )
        logger.info(
            "agent_turn_pass: user=%s session=%s actions=%d",
            user_id,
            session_id,
            actions,
        )
    except Exception as exc:
        # Regla: el worker NUNCA muere por un fallo de la pasada del agente.
        # regla #4: logger.error (NO logger.exception): el traceback / str(exc) podría
        # arrastrar contenido de usuario a los logs. Se loguea solo el TIPO de excepción.
        logger.error(
            "agent_turn_pass: fallo user=%s session=%s: %s (sin datos de usuario)",
            user_id,
            session_id,
            type(exc).__name__,
        )
