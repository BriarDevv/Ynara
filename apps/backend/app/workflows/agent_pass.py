"""Pasada ASÍNCRONA del agente qwen sobre el turno conversado (Fase E, ADR-021).

"qwen por detrás de gemma": el usuario conversa con el modelo conversacional
(respuesta rápida en streaming); ESTA task corre por detrás, async, y a partir de
lo conversado **agenda eventos reales** (y, en fases futuras, recuerda / usa más
tools). Espejo EXACTO de ``consolidate_turn`` (``app/workflows/consolidation.py``):

1. Solo encolada cuando el modo habilita ``calendar`` en ``tools_enabled``. El
   caller (``ChatService._enqueue_agent_pass``) ya filtra; esta task RE-CHEQUEA el
   gate de forma defensiva (un payload viejo / cambio de config entre enqueue y run
   no debe agendar en un modo que ya no habilita calendar).
2. NUNCA en el path de respuesta: ``ChatService.run_turn`` encola con ``.delay()``
   DESPUÉS del commit; el efecto (escribir ``calendar_events``) ocurre acá, en el
   worker Celery, async.
3. Responsabilidad ÚNICA: tools/acciones (calendar). NO toca memoria — eso es
   ``consolidate_turn``, una task separada gateada por ``writes_memory`` (ADR-021
   D3: memoria y tools se operan/escalan/reintentan por separado).
4. Serialización 100% JSON: la firma es solo strings/primitivos. El worker
   RECONSTRUYE sus deps in-process desde ``get_settings()``. El engine de DB usa
   ``NullPool`` obligatorio (igual que la consolidación, decisión #4).
5. IDEMPOTENCIA (ADR-021): la pasada NO debe duplicar acciones ante un reintento de
   Celery. La estrategia es **idempotencia de la tool**: ``calendar.create_event``
   deduplica por la tupla natural ``(user_id, title, start_at, duration_min)`` (ver
   ``CalendarEventStore.create_event``), así re-correr el mismo turno → el mismo
   ``create_event`` → no agenda el evento dos veces. Sumado al at-most-once del
   broker (``task_acks_late=False``), un evento conversado se agenda una sola vez.
   ``MAX_TOOL_ITERATIONS`` (5) acota el loop como en el resto del stack.
6. Ningún dato de usuario a logs (regla #4): el turno queda on-prem en
   Redis/worker; solo se loguea el conteo de acciones y el tipo de excepción.
"""

from __future__ import annotations

import asyncio
import logging
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
from app.workers.celery_app import celery_app
from app.workflows._engine import worker_session

logger = logging.getLogger(__name__)

# Namespace de la tool que habilita esta pasada (ALCANCE Fase E: solo calendar;
# reminders quedan not_wired para Fase F). Si el modo no lo tiene en
# ``tools_enabled``, la pasada NO corre (gate D2/D5 del ADR-021, config-driven).
_CALENDAR_NAMESPACE = "calendar"

# System prompt de la pasada del agente. NO es el prompt conversacional del modo
# (ese lo usa gemma para hablar): este instruye a qwen a OBSERVAR lo conversado y
# AGENDAR si corresponde, sin charlar. Estático (no depende del usuario).
# S105: NO es un secreto — es el system prompt del agente (el nombre contiene
# "SYSTEM" y dispara el falso positivo de hardcoded-password).
_AGENT_PASS_SYSTEM = (
    "Sos el agente de Ynara que trabaja por detrás de la conversación. "  # noqa: S105
    "Recibís un turno ya conversado (mensaje del usuario + respuesta del asistente). "
    "Tu única tarea es AGENDAR en el calendario lo que se haya acordado o pedido: "
    "si el turno implica un evento concreto (con fecha/hora), usá la tool "
    "calendar.create_event con título, start_at (ISO 8601 con huso) y duración en "
    "minutos. Si no hay nada para agendar, no llames ninguna tool y respondé vacío. "
    "No inventes eventos que no estén en lo conversado. No converses con el usuario: "
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


async def _run_agent_pass_in_db(
    *,
    session: AsyncSession,
    user_id: UUID,
    served_name: str,
    user_msg: str,
    model_response: str,
    thinking: bool | None,
    llm_client: LLMClient,
) -> int:
    """Núcleo de la pasada sobre una ``session`` ya abierta. Retorna #acciones ejecutadas.

    Construye el ``CalendarEventStore`` ligado a ``(session, user_id)`` y su
    ``calendar_registry`` REAL, arma ``messages = [system, turno]`` y corre
    ``run_tool_loop`` con SOLO las specs de calendar. Las tool calls que el modelo
    emita se ejecutan (creando eventos reales, idempotentes). NO commitea: el commit
    lo da el caller (``worker_session`` en prod, o el fixture en tests).
    """
    calendar_store = CalendarEventStore(session, user_id)
    calendar_reg = calendar_registry(calendar_store)
    specs = calendar_reg.specs_for([_CALENDAR_NAMESPACE])

    messages = [
        ChatMessage(role="system", content=_AGENT_PASS_SYSTEM),
        ChatMessage(role="user", content=_build_turn_message(user_msg, model_response)),
    ]

    # registries = (calendar_reg, None): SOLO calendar tiene efecto en esta pasada
    # (ALCANCE Fase E). El loop ejecuta cada tool call vía el calendar_registry real.
    _text, actions, _finish_reason = await run_tool_loop(
        llm_client=llm_client,
        served_name=served_name,
        messages=messages,
        specs=specs,
        registries=(calendar_reg, None),
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

    Gate (ADR-021 D2/D5, config-driven): se corre SOLO si el modo habilita
    ``calendar`` en ``tools_enabled``. Si no, retorna 0 sin tocar nada (un modo sin
    calendar no agenda). El gate se re-evalúa acá de forma defensiva: el caller ya
    filtra, pero un payload viejo / cambio de config no debe accionar en un modo que
    ya no habilita calendar.

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
    # Gate: modo desconocido o sin calendar habilitado -> no-op (no se agenda).
    if mode_cfg is None or _CALENDAR_NAMESPACE not in mode_cfg.tools_enabled:
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
