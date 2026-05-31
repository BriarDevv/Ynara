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
- ``route()`` ya NO encola: el ``consolidate_turn.delay()`` vive en el endpoint
  (``_run_chat_turn``), DESPUES del ``session.commit()`` (M10 Ola 0). El router
  solo ensambla contexto + tool loop y devuelve la respuesta; la decision de
  consolidar (``writes_memory`` + turno no-degradado) se evalua en el endpoint.
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

(b) Sin historial multi-turno. ``route()`` arma ``messages`` desde cero
    (system + user actual) en cada llamada. El historial vivo de la sesion es
    M9 (``ChatSession`` persistida). Limitacion conocida de M8.

(c) Captura de overflow / errores permanentes. La llamada al modelo se envuelve
    en ``try/except``: el ``ResilientClient`` RE-LANZA
    ``LlmContextOverflowError`` (error permanente, NO degrada) -> sin captura
    seria un 500 sin fallback en el caso Gemma 4096 ajustado. ``route()``
    captura el overflow (y los errores permanentes del LLM) y devuelve un
    ``ChatResponse`` con texto de fallback en vez de propagar la excepcion.

(d) Encolado de consolidacion (Ola 2; movido en M10 Ola 0). El
    ``consolidate_turn.delay()`` ya NO vive en ``route()``: se movio al endpoint
    (``_run_chat_turn`` en ``app.api.v1.chat``), DESPUES del ``session.commit()``,
    para que la ``ChatSession`` este persistida antes de que el worker Celery
    (otro proceso) procese el turno. El enqueue sigue siendo no-bloqueante y
    condicionado a ``writes_memory`` (Qwen=True, Gemma=False) + turno no-degradado;
    la condicion se replica EXACTA en el endpoint. ``route()`` solo provee la
    respuesta (incluido ``finish_reason``) que el endpoint usa para decidir.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.llm.config import LlmRuntimeConfig, load_llm_config
from app.llm.context import (
    COMPLETION_RESERVE_TOKENS,
    _estimate_tokens,
    build_memory_context,
    render_context_block,
)
from app.llm.errors import LlmBadRequestError
from app.llm.prompts.loader import load_prompt
from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse
from app.llm.tool_loop import run_tool_loop

__all__ = ["ChatRequest", "ChatResponse", "route"]

# Texto que se devuelve cuando el modelo no puede responder (overflow / error
# permanente). Neutro, sin filtrar detalle tecnico (regla #4: ninguna respuesta
# expone internals al usuario).
_FALLBACK_TEXT = (
    "Perdon, no pude procesar tu mensaje en este momento. "
    "Proba de nuevo en un rato o reformulalo mas corto."
)


def _context_budget(*, max_model_len: int, system_prompt: str) -> int:
    """Presupuesto de tokens para el bloque de contexto de memoria.

    Descuenta de ``max_model_len`` la estimacion del system prompt base y el
    ``COMPLETION_RESERVE_TOKENS`` (tokens reservados para la generacion). El
    resultado nunca es negativo: en el peor caso (prompt enorme + ventana
    chica, p.ej. Gemma 4096) devuelve 0. Con budget 0, ``render_context_block``
    igual incluye un PISO MINIMO de las entradas mas relevantes (hasta ~3
    semantic + 1 episodic + 5 procedural, ~200 tokens): el
    ``COMPLETION_RESERVE_TOKENS`` garantiza espacio para ese piso aun en Gemma
    4096, asi que el piso nunca provoca overflow real.

    La estimacion de tokens es la heuristica de ``app.llm.context``
    (``len // 3``), consistente con el truncado de ``render_context_block``.

    Args:
        max_model_len: Ventana de contexto efectiva del modelo (de
            ``serving.max_model_len[model_key]``).
        system_prompt: System prompt base del modo (antes de inyectar memoria).

    Returns:
        Presupuesto en tokens (>= 0) para el bloque de contexto de memoria.
    """
    reserved = _estimate_tokens(system_prompt) + COMPLETION_RESERVE_TOKENS
    return max(0, max_model_len - reserved)


async def route(
    request: ChatRequest,
    *,
    session: AsyncSession,
    user_id: UUID,
    llm_client: LLMClient,
    embedder: EmbeddingClient,
    reranker: Reranker,
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
        (b) sin historial multi-turno: ``messages`` desde cero; historial
            vivo = M9.
        (c) overflow / error permanente del LLM -> ``ChatResponse`` con
            fallback (no se propaga la excepcion).
    """
    cfg = config if config is not None else load_llm_config()

    mode_key = request.mode.value
    mode_cfg = cfg.modes[mode_key]
    model_cfg = cfg.model_for_mode(mode_key)
    max_model_len = cfg.serving.max_model_len[model_cfg.key]

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
    budget = _context_budget(max_model_len=max_model_len, system_prompt=system_prompt)
    context_block = await render_context_block(
        mem_ctx, query=request.text, budget_tokens=budget
    )

    # Concatenar el bloque al system prompt en un STRING NUEVO (decision #6: no
    # mutar el prompt cacheado). Si el bloque esta vacio, el prompt queda igual.
    if context_block:
        final_system = f"{system_prompt}\n\n{context_block}"
    else:
        final_system = system_prompt

    specs = mem_ctx.tool_specs(mode_cfg.tools_enabled)

    # Historial desde cero: system + user actual (sin multi-turno; ver nota (b)).
    messages = [
        ChatMessage(role="system", content=final_system),
        ChatMessage(role="user", content=request.text),
    ]

    session_id = request.session_id or str(uuid4())

    # Envolver el tool loop: el ResilientClient RE-LANZA LlmContextOverflowError
    # y demas errores permanentes (LlmBadRequestError) -> devolvemos fallback en
    # vez de propagar un 500 (ver nota (c)).
    try:
        final_text, actions, finish_reason = await run_tool_loop(
            llm_client=llm_client,
            served_name=model_cfg.served_name,
            messages=messages,
            specs=specs,
            registries=mem_ctx.registries,
            fallback_text=_FALLBACK_TEXT,
        )
    except LlmBadRequestError:
        return ChatResponse(
            text=_FALLBACK_TEXT, actions=[], session_id=session_id, finish_reason="degraded"
        )

    # NO se encola consolidacion aca (M10 Ola 0): el enqueue se movio al endpoint
    # (``_run_chat_turn`` en ``app.api.v1.chat``), DESPUES del ``session.commit()``,
    # para garantizar que la ``ChatSession`` ya este persistida antes de que el
    # worker Celery (otro proceso) lea el turno. ``route()`` ya no encola NADA: la
    # condicion (``writes_memory`` + turno no-degradado) se replica en el endpoint.
    return ChatResponse(
        text=final_text, actions=actions, session_id=session_id, finish_reason=finish_reason
    )
