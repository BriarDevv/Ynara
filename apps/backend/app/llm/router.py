"""Router LLM: ensambla contexto de memoria + tool loop y devuelve la respuesta.

Decision: el modelo a usar viene de ``ynara.config.json[modes][...].model``.
Este archivo NO duplica esa configuracion: la carga en runtime via
``load_llm_config()`` (cacheado a nivel de modulo).

Reglas (M8 Ola 1 + Ola 2; enqueue movido en M10 Ola 0):
- Gemma (conversacional) solo lee memoria: ``tools_enabled=[]`` -> sin tool loop
  real, una sola vuelta al modelo. ``writes_memory=False``: el turno NO se
  consolida.
- Qwen (agent) lee memoria y puede llamar tools (calendar/reminder/memory).
  ``writes_memory=True``: el turno SE consolida en el worker Celery (no
  bloqueante, decision #2 ADR-010).
- ``route()`` ya NO encola: el ``consolidate_turn.delay()`` vive en el service
  (``ChatService.run_turn``), DESPUES del ``session.commit()`` (M10 Ola 0). El router
  solo ensambla contexto + tool loop y devuelve la respuesta; la decision de
  consolidar (``writes_memory`` + turno no-degradado) se evalua en el service.
- El router nunca acepta inputs sin sanear: ``request.mode`` es un ``Mode``
  validado por Pydantic; el ``session_id`` se trata como string opaco DENTRO del
  router (no lo parsea ni lo usa como FK), pero AGUAS ARRIBA es el
  ``ChatSession.id`` real (ver nota (a)).

Flujo de ``route()``:
1. Carga la config del modo (``mode_cfg``), el modelo (``model_cfg``) y el
   ``max_model_len`` del modelo desde ``ynara.config.json``.
2. Carga el system prompt estatico del modo (``load_prompt``, cacheado).
3. Construye el ``MemoryContext`` con SOLO los stores de las layers del modo
   y renderiza el bloque de contexto de memoria respetando un presupuesto de
   tokens (``max_model_len`` - estimacion(system) - ``COMPLETION_RESERVE``).
4. Concatena el bloque al system prompt en un STRING NUEVO (NO muta el prompt
   cacheado) si el bloque no esta vacio.
5. Arma ``messages = [system, user]`` y corre ``run_tool_loop`` con el
   ``served_name`` del modelo (NUNCA la key interna).
6. Devuelve un ``ChatResponse`` con el texto final, las ``actions`` ejecutadas
   y el ``session_id``. ``route()`` NO encola consolidacion: eso lo hace el
   endpoint despues del commit (M10 Ola 0; ver ``app.api.v1.chat``).

Decisiones de diseno documentadas (M8 Ola 1 + Ola 2):

(a) ``session_id`` opaco DENTRO del router. ``route()`` usa
    ``request.session_id`` si viene; si no, genera ``str(uuid4())``. El router NO
    lo parsea a ``UUID`` ni lo usa como FK: es un string que devuelve tal cual en
    el ``ChatResponse``. AGUAS ARRIBA (M9) el endpoint ya pasa
    ``str(ChatSession.id)`` real, y la consolidacion (M10 Ola 1) lo parsea y lo
    persiste como ``source_session_id`` (FK a ``sessions.id``) en el ADD
    semantic. La episodica sigue siendo trabajo aparte
    (``EpisodicMemory.session_id`` es FK NOT NULL a ``sessions.id``).

(b) Historial multi-turno implementado. ``route()`` recibe el param
    ``history`` (turnos previos descifrados, cargados por
    ``ChatService._load_history``) y los inyecta en ``messages`` recortados
    al presupuesto de tokens (``trim_history_to_budget``). Antes de M9 (nota
    histórica) el router armaba solo ``[system, user_actual]`` — ya no aplica.

(c) Captura de la familia ``LlmError`` con UNA excepcion. La llamada al modelo se
    envuelve en ``try/except``: ``route()`` degrada (``ChatResponse`` con
    ``finish_reason="degraded"``) ante los transitorios (``LlmTimeoutError``/
    ``LlmUnavailableError``/``LlmOverloadedError``), permanentes
    (``LlmBadRequestError``/``LlmContextOverflowError``) y semanticos
    (``ToolParsingError``/``ToolExecutionError``), logueando SOLO
    ``type(exc).__name__`` (regla #4) para no degradar a ciegas. La UNICA excepcion
    es ``ModelNotServedError``: NO es degradacion del modelo sino una
    misconfiguracion de deploy (ningun backend del pool sirve el modelo del modo),
    asi que se RE-LANZA (500 + alerta) en vez de enmascararse como un turno
    degradado que el usuario veria como respuesta normal. El ``ResilientClient``
    degrada los transitorios por su cuenta pero RE-LANZA los permanentes y
    ``ModelNotServedError`` (estan en sus ``_PERMANENT_ERRORS``); un ``VllmClient``
    pelado RE-LANZA todo. Asi la promesa "``route()`` nunca propaga un error
    transitorio/permanente del modelo al caller" se cumple con cualquier cliente, y
    un deploy roto sigue siendo ruidoso.

(d) Encolado de consolidacion (Ola 2; movido en M10 Ola 0). El
    ``consolidate_turn.delay()`` ya NO vive en ``route()``: se movio al service
    (``ChatService.run_turn`` en ``app.services.chat``), DESPUES del ``session.commit()``,
    para que la ``ChatSession`` este persistida antes de que el worker Celery
    (otro proceso) procese el turno. El enqueue sigue siendo no-bloqueante y
    condicionado a ``writes_memory`` (Qwen=True, Gemma=False) + turno no-degradado;
    la condicion se replica EXACTA en el endpoint. ``route()`` solo provee la
    respuesta (incluido ``finish_reason``) que el endpoint usa para decidir.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.config import LlmRuntimeConfig, load_llm_config
from app.llm.context import (
    build_memory_context,
    context_budget,
    render_context_block,
    trim_history_to_budget,
)
from app.llm.errors import LlmError, ModelNotServedError
from app.llm.prompts.datetime_context import build_now_preamble, current_now
from app.llm.prompts.loader import load_prompt
from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse
from app.llm.tool_loop import run_tool_loop

__all__ = ["ChatRequest", "ChatResponse", "route"]

logger = logging.getLogger(__name__)

# Texto que se devuelve cuando el modelo no puede responder (overflow / error
# permanente). Neutro, sin filtrar detalle tecnico (regla #4: ninguna respuesta
# expone internals al usuario).
_FALLBACK_TEXT = (
    "Perdon, no pude procesar tu mensaje en este momento. "
    "Proba de nuevo en un rato o reformulalo mas corto."
)


def _thinking_for_role(role: str) -> bool | None:
    """Modo de razonamiento por rol del modelo (ADR-012 D4).

    - ``conversational`` -> ``False``: el modelo conversacional (Gemma 4) NUNCA
      piensa. Con thinking activo Gemma devuelve ``content`` vacio (gotcha medido);
      emitir ``False`` explicito garantiza OFF aunque cambie el default del server.
    - ``agent`` -> ``True``: el agente (Qwen3) piensa para planificar tool calls;
      emitir ``True`` explicito asegura ON aunque cambie el default del server.
    - cualquier otro rol -> ``None``: no emitir la clave, usar el default del
      server. La config tipa ``role`` como ``Literal`` (solo los dos de arriba), asi
      que esta rama es inalcanzable en runtime; existe como fail-safe que NO rompe el
      turno ante un rol desconocido (preserva el comportamiento previo exacto).
    """
    if role == "conversational":
        return False
    if role == "agent":
        return True
    return None


async def route(
    request: ChatRequest,
    *,
    session: AsyncSession,
    user_id: UUID,
    llm_client: LLMClient,
    embedder: EmbeddingClient,
    reranker: Reranker,
    history: list[ChatMessage] | None = None,
    config: LlmRuntimeConfig | None = None,
) -> ChatResponse:
    """Punto de entrada unico al LLM: ensambla contexto + tool loop y responde.

    Args:
        request: Entrada del usuario (``text`` + ``mode`` + ``session_id``
            opcional). El router trata el ``session_id`` opaco (ver nota (a) del
            modulo); aguas arriba es el ``ChatSession.id`` real.
        session: ``AsyncSession`` de la request actual (la usan los stores de
            memoria; el router no commitea nada).
        user_id: UUID del usuario autenticado. Liga la key de cifrado de los
            stores; NO viaja como argumento de ninguna tool (el store ya lo
            tiene). ChatRequest no lo trae: lo provee el endpoint (M9) desde la
            sesion autenticada.
        llm_client: Cliente de inferencia (real ``ResilientClient`` o
            ``FakeLlmClient``). Se le pasa el ``served_name`` del modelo.
        embedder: Cliente de embeddings para semantic/episodic.
        reranker: Cliente de reranking para semantic/episodic.
        config: Config de runtime ya cargada; si es ``None`` usa
            ``load_llm_config()`` (cacheado). Inyectable para tests.

    Returns:
        ``ChatResponse`` con:
        - ``text``: respuesta final del modelo (nunca vacia: usa fallback).
        - ``actions``: lista de tools ejecutadas ``{'name', 'result'}``.
        - ``session_id``: el de la request o uno nuevo ``str(uuid4())`` (opaco
          dentro del router; aguas arriba es el ``ChatSession.id`` real).

    Notas (ver docstring del modulo para el detalle):
        (a) ``session_id`` opaco dentro del router; aguas arriba es el
            ``ChatSession.id`` real y la consolidacion (M10 Ola 1) lo persiste
            como ``source_session_id`` en el ADD semantic.
        (b) historial multi-turno inyectado vía param ``history`` y recortado
            al presupuesto de tokens por ``trim_history_to_budget``.
        (c) cualquier error de la familia ``LlmError`` (permanente O transitorio)
            -> ``ChatResponse`` degradado con fallback (no se propaga la excepcion).
    """
    cfg = config if config is not None else load_llm_config()

    mode_key = request.mode.value
    mode_cfg = cfg.modes[mode_key]
    model_cfg = cfg.model_for_mode(mode_key)
    max_model_len = cfg.serving.max_model_len[model_cfg.key]

    # Modo de razonamiento por rol (ADR-012 D4): conversacional NUNCA piensa
    # (Gemma -> content vacio con thinking ON), agente SI (Qwen planifica tool
    # calls). Se hila por el tool loop hasta el cliente; ``None`` deja el default.
    thinking = _thinking_for_role(model_cfg.role)

    # System prompt estatico del modo (cacheado, NO mutar).
    system_prompt = load_prompt(request.mode)

    # Contexto de memoria: solo los stores de las layers del modo.
    mem_ctx = build_memory_context(
        session=session,
        user_id=user_id,
        embedder=embedder,
        reranker=reranker,
        mode_cfg=mode_cfg,
    )
    # Preambulo de fecha/hora actual (timezone-aware, huso de la app). Cierra el gap
    # E2E: sin esto el modelo NO podia resolver fechas relativas ("mañana", "el lunes")
    # al agendar. Se construye por-run con current_now() (lee el reloj una sola vez aca);
    # NO se cachea porque cambia cada minuto. Se arma ANTES del budget a proposito: el
    # bloque de memoria debe dimensionarse reservando tambien los tokens del preambulo
    # (si se calculaba el budget con el prompt pelado, el bloque quedaba sobre-asignado y
    # final_system podia excederse de max_model_len).
    now_preamble = build_now_preamble(current_now())

    # Base del system para el budget: preambulo + prompt del modo (STRING NUEVO; decision
    # #6: no mutar el prompt cacheado). El bloque de memoria se dimensiona contra ESTA base
    # (reserva el preambulo) y final_system se arma sobre la misma base. El preambulo va al
    # inicio para que el modelo ancle las fechas relativas antes de leer el resto.
    base_system = f"{now_preamble}\n\n{system_prompt}"
    budget = context_budget(max_model_len=max_model_len, system_prompt=base_system)
    context_block = await render_context_block(mem_ctx, query=request.text, budget_tokens=budget)

    # Si el bloque de memoria esta vacio, final_system es solo la base (preambulo + prompt).
    if context_block:
        final_system = f"{base_system}\n\n{context_block}"
    else:
        final_system = base_system

    specs = mem_ctx.tool_specs(mode_cfg.tools_enabled)

    # Historial multi-turno: los turnos previos de la sesión (user/assistant alternados)
    # le dan continuidad a la conversación. Sin esto el modelo recibía SOLO el system + el
    # mensaje actual y trataba cada turno como una persona nueva (nota (b), ahora resuelta).
    # El caller (``ChatService.run_turn``) carga los turnos descifrados desde
    # ``conversation_turns``; acá se recortan al presupuesto de la ventana (más recientes
    # primero, turnos completos, orden cronológico) para no desbordar ``max_model_len`` —
    # crítico en Gemma (ventana servida 8192). ``final_system`` ya incluye preámbulo +
    # bloque de memoria, así que el recorte reserva ese tamaño + el mensaje actual + la
    # completion. messages = [system, *historial_recortado, user_actual].
    budgeted_history = trim_history_to_budget(
        history or [],
        max_model_len=max_model_len,
        system_prompt=final_system,
        current_user=request.text,
    )
    messages = [
        ChatMessage(role="system", content=final_system),
        *budgeted_history,
        ChatMessage(role="user", content=request.text),
    ]

    session_id = request.session_id or str(uuid4())

    # Envolver el tool loop capturando la familia LlmError, con UNA excepcion: un
    # ModelNotServedError NO es degradacion del modelo sino misconfiguracion de
    # deploy (ningun backend del pool sirve el modelo del modo) -> debe propagar
    # (500 + alerta), no enmascararse como turno degradado que el usuario ve normal.
    # El resto de la familia (transitorios timeout/unavailable/overloaded,
    # permanentes bad-request/overflow, semanticos parse/exec) significa "el turno no
    # se pudo completar" -> fallback degradado. El ResilientClient degrada los
    # transitorios solo, pero RE-LANZA los permanentes y ModelNotServedError (estan en
    # sus _PERMANENT_ERRORS) y un VllmClient pelado RE-LANZA todo: este except es la
    # red real. Se loguea SOLO type(exc).__name__ (regla #4) para no degradar a ciegas.
    try:
        final_text, actions, finish_reason = await run_tool_loop(
            llm_client=llm_client,
            served_name=model_cfg.served_name,
            messages=messages,
            specs=specs,
            registries=mem_ctx.registries,
            thinking=thinking,
            fallback_text=_FALLBACK_TEXT,
        )
    except ModelNotServedError:
        # Config/deploy roto: alertar, NO degradar en silencio.
        logger.error("route: modelo no servido (config/deploy)")
        raise
    except LlmError as exc:
        logger.warning("route degrado por error LLM: %s", type(exc).__name__)
        return ChatResponse(
            text=_FALLBACK_TEXT, actions=[], session_id=session_id, finish_reason="degraded"
        )

    # NO se encola consolidacion aca (M10 Ola 0): el enqueue se movio al service
    # (``ChatService.run_turn`` en ``app.services.chat``), DESPUES del ``session.commit()``,
    # para garantizar que la ``ChatSession`` ya este persistida antes de que el
    # worker Celery (otro proceso) lea el turno. ``route()`` ya no encola NADA: la
    # condicion (``writes_memory`` + turno no-degradado) se replica en el service.
    return ChatResponse(
        text=final_text, actions=actions, session_id=session_id, finish_reason=finish_reason
    )
