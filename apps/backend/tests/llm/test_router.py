"""Tests de app/llm/router.py (M8 Ola 1).

UNIT (sin DB, sin marker): testean ``_context_budget`` y los caminos de
``route()`` que no requieren memoria sembrada (overflow -> fallback,
session_id generado, served_name correcto). Usan ``FakeLlmClient`` +
``FakeEmbeddingClient`` + ``FakeReranker`` + un ``AsyncSession`` mockeado
(los stores no llegan a ejecutar query porque el modo no tiene layers o
porque la search se mockea). La config se inyecta para no depender del
``ynara.config.json`` real... salvo donde queremos el contrato real.

INTEGRATION (@pytest.mark.integration, db_session): siembran user + memorias
reales y verifican el flujo end-to-end por modo:
- Gemma (vida): lee memoria por prompt (el system prompt del complete_calls
  contiene el bloque de contexto), specs vacios, 1 vuelta, devuelve text.
- Qwen (productividad): tool loop con memory.search, actions poblado,
  served_name='qwen' en complete_calls.
- session_id generado si request.session_id is None.
- Overflow -> ChatResponse con fallback, sin excepcion.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.enums import Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.config import load_llm_config
from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmTimeoutError,
)
from app.llm.router import route
from app.llm.schemas import ChatRequest, CompletionResult, ToolCall

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result(
    *,
    text: str = "hola",
    finish_reason: str = "stop",
    tool_calls: list[ToolCall] | None = None,
    model_name: str = "qwen",
) -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason=finish_reason,
        tool_calls=tool_calls or [],
        prompt_tokens=10,
        completion_tokens=5,
        model_name=model_name,
        latency_ms=42.0,
    )


def _cfg() -> Any:
    """Config real del ynara.config.json (contrato de producto)."""
    return load_llm_config()


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# UNIT: _context_budget
# ---------------------------------------------------------------------------


def test_context_budget_subtracts_system_and_reserve() -> None:
    from app.llm.context import COMPLETION_RESERVE_TOKENS, _estimate_tokens
    from app.llm.router import _context_budget

    prompt = "x" * 300
    budget = _context_budget(max_model_len=4096, system_prompt=prompt)
    expected = 4096 - _estimate_tokens(prompt) - COMPLETION_RESERVE_TOKENS
    assert budget == expected


def test_context_budget_never_negative() -> None:
    from app.llm.router import _context_budget

    # Ventana minuscula: el presupuesto cae a 0, nunca negativo.
    budget = _context_budget(max_model_len=10, system_prompt="x" * 5000)
    assert budget == 0


# ---------------------------------------------------------------------------
# UNIT: overflow / errores permanentes -> fallback (sin DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overflow_returns_fallback_not_exception() -> None:
    """Overflow -> ChatResponse con fallback, no excepcion.

    Se parchea ``build_memory_context`` para devolver un contexto sin stores
    activos (asi no se toca DB en este test puro): el foco es la captura del
    overflow, no la inyeccion de memoria (cubierta por los integration).
    """
    from app.llm.router import _FALLBACK_TEXT

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(LlmContextOverflowError("contexto excedido"))

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        resp = await route(
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-1"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.text == _FALLBACK_TEXT
    assert resp.actions == []
    assert resp.session_id == "sess-1"


@pytest.mark.asyncio
async def test_bad_request_error_returns_fallback() -> None:
    """Un LlmBadRequestError generico (no overflow) tambien cae al fallback."""
    from app.llm.router import _FALLBACK_TEXT

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(LlmBadRequestError("request invalido"))

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        resp = await route(
            ChatRequest(text="hola", mode=Mode.VIDA),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.text == _FALLBACK_TEXT


@pytest.mark.asyncio
async def test_transient_error_propagates() -> None:
    """Un error transitorio (timeout) NO se captura: se propaga (lo maneja el
    ResilientClient/pool aguas arriba, no el router)."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(LlmTimeoutError("timeout"))

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        with pytest.raises(LlmTimeoutError):
            await route(
                ChatRequest(text="hola", mode=Mode.VIDA),
                session=MagicMock(),
                user_id=uuid.uuid4(),
                llm_client=fake,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
            )
    finally:
        router_mod.build_memory_context = original


@pytest.mark.asyncio
async def test_session_id_generated_when_none() -> None:
    """Si request.session_id is None, route genera un str(uuid4()) opaco."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="hola!", finish_reason="stop", model_name="gemma4"))

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        resp = await route(
            ChatRequest(text="hola", mode=Mode.VIDA, session_id=None),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.session_id is not None
    # Es un UUID valido en formato str (opaco, pero bien formado).
    uuid.UUID(resp.session_id)
    assert resp.text == "hola!"


@pytest.mark.asyncio
async def test_session_id_preserved_when_provided() -> None:
    """Si request.session_id viene, route lo respeta tal cual (opaco)."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="ok", finish_reason="stop", model_name="gemma4"))

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        resp = await route(
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="no-soy-un-uuid"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.session_id == "no-soy-un-uuid"


# ===========================================================================
# INTEGRATION
# ===========================================================================


async def _seed_user(session: Any) -> Any:
    from app.models.user import User

    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: Any, user: Any) -> Any:
    from app.models.session import ChatSession

    chat = ChatSession(user_id=user.id, mode=Mode.PRODUCTIVIDAD)
    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    return chat


@pytest.mark.integration
async def test_integration_gemma_reads_memory_via_prompt(db_session: Any) -> None:
    """Modo Gemma (vida): el bloque de contexto de memoria se inyecta en el
    system prompt que llega a complete(); specs vacios; 1 vuelta; devuelve text.
    """
    from app.memory.procedural import ProceduralMemoryStore
    from app.schemas.memory import ProceduralMemoryUpsert

    user = await _seed_user(db_session)

    proc_store = ProceduralMemoryStore(db_session, user.id)
    await proc_store.upsert(ProceduralMemoryUpsert(key="pref.idioma", value={"idioma": "es"}))

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="Hola, todo bien?", finish_reason="stop", model_name="gemma4"))

    resp = await route(
        ChatRequest(text="como va?", mode=Mode.VIDA),
        session=db_session,
        user_id=user.id,
        llm_client=fake,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        config=_cfg(),
    )

    assert resp.text == "Hola, todo bien?"
    assert resp.actions == []
    assert len(fake.complete_calls) == 1

    # specs vacios: Gemma conversacional no ve tools.
    assert fake.complete_calls[0]["tools"] is None

    # El system prompt que llego al modelo contiene el bloque de contexto.
    messages = fake.complete_calls[0]["messages"]
    system_msg = messages[0]
    assert system_msg.role == "system"
    assert "Contexto de memoria" in system_msg.content
    assert "pref.idioma" in system_msg.content

    # served_name correcto: gemma4 (no la key interna).
    assert fake.complete_calls[0]["model"] == "gemma4"


@pytest.mark.integration
async def test_integration_qwen_tool_loop_memory_search(db_session: Any) -> None:
    """Modo Qwen (productividad): tool loop con memory.search.

    Vuelta 1: tool_call memory.search; vuelta 2: stop con texto. actions poblado;
    served_name='qwen' en complete_calls.
    """
    from app.memory.semantic import SemanticMemoryStore
    from app.schemas.memory import SemanticMemoryCreate

    user = await _seed_user(db_session)

    sem_store = SemanticMemoryStore(db_session, user.id, FakeEmbeddingClient(), FakeReranker())
    await sem_store.add(SemanticMemoryCreate(content="prefiere reuniones cortas"))

    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    tc = ToolCall(id="tc-1", name="memory.search", arguments={"query": "reuniones"})
    fake.queue_result(
        _result(text="", finish_reason="tool_calls", tool_calls=[tc], model_name="qwen")
    )
    fake.queue_result(
        _result(text="Programe la reunion corta.", finish_reason="stop", model_name="qwen")
    )

    resp = await route(
        ChatRequest(text="agenda una reunion", mode=Mode.PRODUCTIVIDAD, session_id="s-prod"),
        session=db_session,
        user_id=user.id,
        llm_client=fake,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        config=_cfg(),
    )

    assert resp.text == "Programe la reunion corta."
    assert resp.session_id == "s-prod"

    # actions poblado con la memory.search ejecutada.
    assert len(resp.actions) == 1
    assert resp.actions[0]["name"] == "memory.search"
    assert "results" in resp.actions[0]["result"]

    # 2 vueltas al LLM.
    assert len(fake.complete_calls) == 2

    # served_name correcto: qwen (NUNCA la key 'qwen-3.5-9b').
    assert fake.complete_calls[0]["model"] == "qwen"

    # En la primera vuelta, Qwen ve tools (specs no vacios: calendar/reminder/memory).
    first_tools = fake.complete_calls[0]["tools"]
    assert first_tools is not None
    tool_names = {t.name for t in first_tools}
    assert "memory.search" in tool_names


@pytest.mark.integration
async def test_integration_qwen_served_name_and_context(db_session: Any) -> None:
    """Qwen (productividad): el system prompt lleva el bloque de contexto con los
    hechos semanticos sembrados, y se pasa served_name='qwen'."""
    from app.memory.semantic import SemanticMemoryStore
    from app.schemas.memory import SemanticMemoryCreate

    user = await _seed_user(db_session)

    sem_store = SemanticMemoryStore(db_session, user.id, FakeEmbeddingClient(), FakeReranker())
    await sem_store.add(SemanticMemoryCreate(content="trabaja en inteligencia artificial"))

    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_result(text="listo", finish_reason="stop", model_name="qwen"))

    await route(
        ChatRequest(text="que sabes de mi?", mode=Mode.PRODUCTIVIDAD),
        session=db_session,
        user_id=user.id,
        llm_client=fake,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        config=_cfg(),
    )

    messages = fake.complete_calls[0]["messages"]
    system_msg = messages[0]
    assert "Contexto de memoria" in system_msg.content
    assert "trabaja en inteligencia artificial" in system_msg.content
    assert fake.complete_calls[0]["model"] == "qwen"


@pytest.mark.integration
async def test_integration_overflow_returns_fallback(db_session: Any) -> None:
    """Overflow real (queue_error LlmContextOverflowError) -> ChatResponse con
    fallback, sin excepcion."""
    from app.llm.router import _FALLBACK_TEXT

    user = await _seed_user(db_session)

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(LlmContextOverflowError("contexto excedido"))

    resp = await route(
        ChatRequest(text="hola", mode=Mode.VIDA, session_id="s-overflow"),
        session=db_session,
        user_id=user.id,
        llm_client=fake,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        config=_cfg(),
    )

    assert resp.text == _FALLBACK_TEXT
    assert resp.actions == []
    assert resp.session_id == "s-overflow"


@pytest.mark.integration
async def test_integration_user_no_memory_no_context_block(db_session: Any) -> None:
    """Usuario nuevo sin memorias: el system prompt NO lleva bloque de contexto
    (no hay 'Contexto de memoria'), pero el flujo responde igual."""
    user = await _seed_user(db_session)

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="hola nuevo!", finish_reason="stop", model_name="gemma4"))

    resp = await route(
        ChatRequest(text="hola", mode=Mode.VIDA),
        session=db_session,
        user_id=user.id,
        llm_client=fake,
        embedder=FakeEmbeddingClient(),
        reranker=FakeReranker(),
        config=_cfg(),
    )

    assert resp.text == "hola nuevo!"
    messages = fake.complete_calls[0]["messages"]
    system_msg = messages[0]
    assert "Contexto de memoria" not in system_msg.content
