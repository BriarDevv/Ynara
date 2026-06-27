"""Tests de app/llm/router.py (M8 Ola 1).

UNIT (sin DB, sin marker): testean los caminos de ``route()`` que no requieren
memoria sembrada (overflow -> fallback, session_id generado, served_name
correcto) y que ``route()`` consume el presupuesto publico ``context_budget``
de ``app.llm.context`` (la formula del presupuesto se testea en
``test_context.py``). Usan ``FakeLlmClient`` +
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
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelNotServedError,
    ToolParsingError,
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
# UNIT: route() consume el presupuesto publico context_budget
# ---------------------------------------------------------------------------


def test_router_imports_public_budget_not_private() -> None:
    """``route()`` consume las publicas de ``app.llm.context`` (desacople P2.2).

    Guardia del refactor: el router NO debe reimplementar el presupuesto ni
    importar el privado ``_estimate_tokens``. La unica sede de la formula es
    ``app.llm.context.context_budget`` (testeada en ``test_context.py``).
    """
    from app.llm import context as ctx_mod
    from app.llm import router as router_mod

    # La pública vive en context y el router la importa (mismo objeto).
    assert router_mod.context_budget is ctx_mod.context_budget
    # El router ya NO expone la duplicada ni el privado promovido.
    assert not hasattr(router_mod, "_context_budget")
    assert not hasattr(router_mod, "_estimate_tokens")


@pytest.mark.asyncio
async def test_route_uses_context_budget_for_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """``route()`` calcula el budget con ``context_budget`` y se lo pasa a
    ``render_context_block`` tal cual (sin recalcular la cuenta en el router).
    """
    from app.llm import router as router_mod
    from app.llm.context import MemoryContext, context_budget
    from app.llm.tools.registry import default_registry

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="ok", finish_reason="stop", model_name="gemma4"))

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )

    captured: dict[str, int] = {}

    async def _fake_render(_ctx: Any, *, query: str, budget_tokens: int) -> str:
        captured["budget"] = budget_tokens
        return ""

    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    monkeypatch.setattr(router_mod, "render_context_block", _fake_render)

    cfg = _cfg()
    model_cfg = cfg.model_for_mode(Mode.VIDA.value)
    max_model_len = cfg.serving.max_model_len[model_cfg.key]
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.llm.prompts.datetime_context import build_now_preamble
    from app.llm.prompts.loader import load_prompt

    # El budget reserva el preambulo de fecha + el prompt del modo (route() lo arma ANTES
    # del budget para no sobre-asignar el bloque de memoria). Se fija current_now para que
    # el preambulo sea determinista y el expected coincida con lo que recibe render.
    fixed = datetime(2026, 7, 22, 18, 30, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    # ``current_now`` ahora acepta ``tz``: el stub ignora el arg y devuelve el fijo.
    monkeypatch.setattr(router_mod, "current_now", lambda *_a, **_k: fixed)
    # route() ahora nombra el huso (``tz_label=tz``, default APP_TIMEZONE): el budget se
    # mide contra el MISMO preámbulo que arma route, así que el expected lo replica.
    base_system = (
        f"{build_now_preamble(fixed, tz_label='America/Argentina/Buenos_Aires')}"
        f"\n\n{load_prompt(Mode.VIDA)}"
    )
    expected = context_budget(max_model_len=max_model_len, system_prompt=base_system)

    try:
        await route(
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-budget"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            config=cfg,
        )
    finally:
        router_mod.build_memory_context = original

    assert captured["budget"] == expected


# ---------------------------------------------------------------------------
# UNIT: thinking por rol (ADR-012 D4, #205)
# ---------------------------------------------------------------------------


def test_thinking_for_role() -> None:
    """``_thinking_for_role`` mapea rol -> flag (ADR-012 D4).

    Cubre tambien la rama ``None`` (rol desconocido), inalcanzable en runtime
    porque la config tipa ``role`` como ``Literal``, pero presente como fail-safe
    que no rompe el turno.
    """
    from app.llm.router import _thinking_for_role

    assert _thinking_for_role("conversational") is False
    assert _thinking_for_role("agent") is True
    assert _thinking_for_role("otro") is None


@pytest.mark.asyncio
async def test_route_conversational_mode_disables_thinking() -> None:
    """Modo conversacional (VIDA -> gemma4) deriva ``thinking=False`` al complete.

    El conversacional NUNCA piensa (Gemma -> content vacio con thinking ON).
    """
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="hola", finish_reason="stop", model_name="gemma4"))

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
        await route(
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-think-conv"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            config=_cfg(),
        )
    finally:
        router_mod.build_memory_context = original

    assert fake.complete_calls[0]["thinking"] is False


@pytest.mark.asyncio
async def test_route_agent_mode_enables_thinking() -> None:
    """Modo agente (PRODUCTIVIDAD -> qwen) deriva ``thinking=True`` al complete.

    El agente piensa para planificar tool calls (Qwen).
    """
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_result(text="listo", finish_reason="stop", model_name="qwen"))

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
        await route(
            ChatRequest(text="hola", mode=Mode.PRODUCTIVIDAD, session_id="sess-think-agent"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            config=_cfg(),
        )
    finally:
        router_mod.build_memory_context = original

    assert fake.complete_calls[0]["thinking"] is True


# ---------------------------------------------------------------------------
# UNIT: preambulo de fecha/hora actual en el system (gap E2E)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_injects_datetime_preamble_in_system() -> None:
    """``route()`` antepone el preambulo de fecha/hora actual al system prompt.

    Cierra el gap E2E: sin esto el modelo no podia resolver "mañana"/"el lunes" al
    agendar. Se parchea ``current_now`` a una fecha fija para verificar el string
    determinista que llega al complete().
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="ok", finish_reason="stop", model_name="gemma4"))

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    fixed = datetime(2026, 7, 22, 18, 30, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))

    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(router_mod, "current_now", lambda *_a, **_k: fixed)
            await route(
                ChatRequest(text="agendame gym mañana 18hs", mode=Mode.VIDA, session_id="s-dt"),
                session=MagicMock(),
                user_id=uuid.uuid4(),
                llm_client=fake,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
                config=_cfg(),
            )
    finally:
        router_mod.build_memory_context = original

    system_msg = fake.complete_calls[0]["messages"][0]
    assert system_msg.role == "system"
    # El preambulo va al inicio del system (ancla la fecha antes del resto).
    assert system_msg.content.startswith("Fecha y hora actual: ")
    # 2026-07-22 cae miércoles (el dia se deriva con weekday(), no se hardcodea). El
    # preámbulo ahora nombra el huso (``tz_label``) en vez de la frase genérica "hora local".
    assert (
        "miércoles 22 de julio de 2026, 18:30 "
        "(hora de America/Argentina/Buenos_Aires, offset UTC-03:00)" in system_msg.content
    )
    assert "resolver fechas relativas" in system_msg.content


@pytest.mark.asyncio
async def test_route_splices_history_between_system_and_user() -> None:
    """``route()`` inserta el historial multi-turno entre el system y el mensaje actual.

    Sin esto el modelo recibía solo [system, user_actual] y trataba cada turno como una
    persona nueva (nota (b) del router, ahora resuelta). Se le pasa un historial y se
    verifica que llega al complete() en orden cronológico, con roles correctos, ENTRE el
    system y el user actual (que va último).
    """
    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.schemas import ChatMessage
    from app.llm.tools.registry import default_registry

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_result(text="Te llamás Mateo.", finish_reason="stop", model_name="gemma4"))

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    history = [
        ChatMessage(role="user", content="me llamo Mateo"),
        ChatMessage(role="assistant", content="Hola Mateo, anotado."),
    ]

    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx
    try:
        await route(
            ChatRequest(text="¿cómo me llamo?", mode=Mode.VIDA, session_id="s-hist"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            history=history,
            config=_cfg(),
        )
    finally:
        router_mod.build_memory_context = original

    messages = fake.complete_calls[0]["messages"]
    assert messages[0].role == "system"
    # Historial entre el system y el mensaje actual, en orden cronológico:
    assert (messages[1].role, messages[1].content) == ("user", "me llamo Mateo")
    assert (messages[2].role, messages[2].content) == ("assistant", "Hola Mateo, anotado.")
    # El mensaje actual va ÚLTIMO:
    assert (messages[-1].role, messages[-1].content) == ("user", "¿cómo me llamo?")
    assert len(messages) == 4


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
    # Overflow se captura via `except LlmError` (raiz) -> finish_reason='degraded'
    assert resp.finish_reason == "degraded"


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
    assert resp.finish_reason == "degraded"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transient_exc",
    [
        LlmTimeoutError("timeout"),
        LlmUnavailableError("instancia caida"),
        LlmOverloadedError("429"),
    ],
)
async def test_transient_error_returns_fallback(transient_exc: LlmError) -> None:
    """Un error transitorio (timeout / instancia caida / sobrecarga) tambien degrada.

    P0.2: con un cliente LLM pelado (sin ResilientClient de por medio) que lanza
    directamente un error transitorio, ``route()`` lo captura via ``except
    LlmError`` y DEVUELVE una ``ChatResponse`` degradada en vez de propagar la
    excepcion (que aguas arriba seria un 500). Asi la promesa "route() nunca
    propaga una excepcion de infra al caller" se cumple con cualquier cliente.
    """
    from app.llm.router import _FALLBACK_TEXT

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(transient_exc)

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
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-transient"),
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
    assert resp.session_id == "sess-transient"
    assert resp.finish_reason == "degraded"


@pytest.mark.asyncio
async def test_model_not_served_propagates() -> None:
    """P0.2: ``ModelNotServedError`` NO degrada — propaga (config/deploy roto).

    Un modelo no servido es una misconfiguracion de deploy, no una degradacion del
    modelo: debe subir como 500 alertable, no enmascararse como un turno 'degraded'
    que el usuario veria como respuesta normal. ``route()`` lo RE-LANZA (a diferencia
    del resto de la familia ``LlmError``, que degrada).
    """
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(ModelNotServedError("qwen"))

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
        with pytest.raises(ModelNotServedError):
            await route(
                ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-notserved"),
                session=MagicMock(),
                user_id=uuid.uuid4(),
                llm_client=fake,
                embedder=FakeEmbeddingClient(),
                reranker=FakeReranker(),
            )
    finally:
        router_mod.build_memory_context = original


@pytest.mark.asyncio
async def test_semantic_tool_parsing_error_degrades() -> None:
    """P0.2: un error SEMANTICO (``ToolParsingError``) tambien degrada.

    Una tool call malformada del modelo (parser hermes/gemma4) sale de
    ``complete()`` como ``ToolParsingError`` (subclase de ``LlmError``); ``route()``
    la captura y degrada en vez de propagar un 500, dejando constancia en el log
    (solo ``type(exc).__name__``). Fija el contrato de la familia semantica.
    """
    from app.llm.router import _FALLBACK_TEXT

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(ToolParsingError("hermes"))

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
            ChatRequest(text="hola", mode=Mode.VIDA, session_id="sess-semantic"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.text == _FALLBACK_TEXT
    assert resp.finish_reason == "degraded"


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
    assert resp.finish_reason == "stop"


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

    M10 Ola 0: ``route()`` ya NO encola consolidacion (el enqueue se movio al
    endpoint, post-commit), asi que aca no hace falta parchear nada: el router
    no toca Redis. El encolado se cubre en los E2E de ``tests/api/``.
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
    action = resp.actions[0]
    assert action["id"] == "tc-1"
    assert action["name"] == "memory.search"
    assert action["arguments"] == {"query": "reuniones"}
    assert "results" in action["result"]
    # finish_reason del loop: stop (segunda vuelta)
    assert resp.finish_reason == "stop"

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
    hechos semanticos sembrados, y se pasa served_name='qwen'.

    M10 Ola 0: ``route()`` ya NO encola consolidacion (movido al endpoint,
    post-commit), asi que este test no parchea nada: solo verifica el contexto de
    memoria inyectado.
    """
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
    assert resp.finish_reason == "degraded"


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


# ===========================================================================
# UNIT: route() NO encola consolidacion (M10 Ola 0)
# ===========================================================================
#
# El enqueue de ``consolidate_turn`` se movio de ``route()`` al endpoint
# (``ChatService.run_turn`` en ``app.services.chat``), DESPUES del ``session.commit()``,
# para blindar a M10 contra un race enqueue-vs-commit cuando escriba FKs a
# ``sessions.id`` (decision M10 Ola 0). El router ya NO importa ``consolidate_turn``
# ni llama ``.delay()`` bajo NINGUN modo. La cobertura del encolado por modo
# (Qwen/memoria encolan, Gemma/estudio no) vive ahora en los E2E de
# ``tests/api/test_chat.py`` y ``tests/api/test_chat_stream.py``, que ejercitan la
# condicion real (``writes_memory`` + turno no-degradado) post-commit.


def test_router_module_no_longer_imports_consolidate_turn() -> None:
    """``route()`` ya no encola: el modulo router NO expone ``consolidate_turn``.

    Guardia contra una regresion del refactor M10 Ola 0 (+ Ola 2): si alguien
    re-introduce el enqueue en ``route()`` (re-importando ``consolidate_turn`` en el
    modulo del router LLM), este test falla. El binding canonico del enqueue es ahora
    ``app.services.chat.consolidate_turn`` (lo usa ``ChatService.run_turn``, sede unica).
    """
    from app.llm import router as router_mod
    from app.services import chat as chat_svc

    # El router LLM NO tiene binding a consolidate_turn (no lo importa).
    assert not hasattr(router_mod, "consolidate_turn"), (
        "route() no debe importar consolidate_turn: el enqueue vive en ChatService (M10 Ola 0)"
    )
    # El ChatService SI lo tiene: es la sede unica del enqueue post-commit.
    assert hasattr(chat_svc, "consolidate_turn"), (
        "el enqueue debe vivir en app.services.chat (sede unica, post-commit)"
    )


@pytest.mark.asyncio
async def test_route_does_not_enqueue_under_any_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Para cualquier modo (Qwen incluido), ``route()`` NO llama ``.delay()``.

    Se inyecta un ``consolidate_turn`` falso en el modulo router (atributo que
    el codigo refactorizado YA NO tiene): si ``route()`` lo llamara, ``delay``
    registraria la llamada. Como el refactor saco el enqueue, ``delay_calls``
    queda vacio para Qwen (productividad, ``writes_memory=True``), que era el
    unico camino que antes encolaba.
    """
    from app.llm import router as router_mod
    from app.llm.context import MemoryContext
    from app.llm.tools.registry import default_registry

    delay_calls: list[dict[str, str]] = []

    class _FakeTask:
        def delay(self, **kwargs: str) -> None:
            delay_calls.append(dict(kwargs))

    # setattr (no monkeypatch.setattr con raising): el atributo ya no existe en
    # el modulo, asi que lo creamos como honeypot; route() NO debe tocarlo.
    monkeypatch.setattr(router_mod, "consolidate_turn", _FakeTask(), raising=False)

    empty_ctx = MemoryContext(
        semantic_store=None,
        episodic_store=None,
        procedural_store=None,
        _default_reg=default_registry(),
        _memory_reg=None,
    )
    original = router_mod.build_memory_context
    router_mod.build_memory_context = lambda **_kw: empty_ctx

    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_result(text="listo qwen", finish_reason="stop", model_name="qwen"))

    try:
        resp = await route(
            ChatRequest(text="hola qwen", mode=Mode.PRODUCTIVIDAD, session_id="sess-qwen"),
            session=MagicMock(),
            user_id=uuid.uuid4(),
            llm_client=fake,
            embedder=FakeEmbeddingClient(),
            reranker=FakeReranker(),
            config=_cfg(),
        )
    finally:
        router_mod.build_memory_context = original

    assert resp.text == "listo qwen"
    assert delay_calls == [], "route() NO debe encolar consolidacion (movido al endpoint)"
