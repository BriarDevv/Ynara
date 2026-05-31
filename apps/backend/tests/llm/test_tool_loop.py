"""Tests de app/llm/tool_loop.py (M8 Ola 1).

Unit: usa FakeLlmClient + ToolRegistry stub. Sin DB.

Escenarios:
- Gemma sin specs: 1 vuelta, termina sin tools.
- Qwen 1 vuelta con tool call que termina con stop.
- Qwen 2 vueltas: tool call en la primera, stop en la segunda.
- Guard de MAX_TOOL_ITERATIONS sin converger -> fallback_text.
- unknown_tool -> tool_error en el resultado de esa action.
- degraded finish_reason -> termina sin ejecutar tools.
- result.text vacio al final -> fallback_text.
- specs vacia -> tools=None en complete (Gemma conversacional).
"""

from __future__ import annotations

import json

import pytest

from app.llm.clients.fakes import FakeLlmClient
from app.llm.schemas import (
    ChatMessage,
    CompletionResult,
    ToolCall,
    ToolSpec,
)
from app.llm.tool_loop import MAX_TOOL_ITERATIONS, _execute_anywhere, run_tool_loop
from app.llm.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    *,
    text: str = "hola",
    finish_reason: str = "stop",
    tool_calls: list[ToolCall] | None = None,
) -> CompletionResult:
    """Construye un CompletionResult con los campos minimos."""
    return CompletionResult(
        text=text,
        finish_reason=finish_reason,
        tool_calls=tool_calls or [],
        prompt_tokens=10,
        completion_tokens=5,
        model_name="gemma4",
        latency_ms=42.0,
    )


def _make_tool_call(name: str = "calendar.create_event", tc_id: str = "tc-1") -> ToolCall:
    return ToolCall(id=tc_id, name=name, arguments={"title": "reunion"})


def _empty_registries() -> tuple[ToolRegistry, None]:
    """Registry vacio (no tiene tools) + None."""
    return (ToolRegistry(), None)


def _messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="Sos Ynara."),
        ChatMessage(role="user", content="Hola"),
    ]


# ---------------------------------------------------------------------------
# Tests: escenarios basicos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemma_sin_specs_una_vuelta() -> None:
    """Gemma (specs=[]) termina en 1 vuelta sin ejecutar ninguna tool."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_make_result(text="Hola! En que te ayudo?", finish_reason="stop"))

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="gemma4",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        fallback_text="lo siento, no pude responder",
    )

    assert text == "Hola! En que te ayudo?"
    assert actions == []
    assert finish_reason == "stop"
    # Solo 1 llamada al LLM
    assert len(fake.complete_calls) == 1
    # specs=[] debe traducirse a tools=None en complete
    assert fake.complete_calls[0]["tools"] is None


@pytest.mark.asyncio
async def test_qwen_1_vuelta_con_tool_call() -> None:
    """Qwen hace 1 tool call y luego devuelve stop."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-abc")
    # Primera respuesta: tool call
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # Segunda respuesta: stop con texto final
    fake.queue_result(_make_result(text="Listo, evento creado.", finish_reason="stop"))

    # Registry con una tool fake que devuelve ok
    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "ok", "event_id": "ev-1"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea un evento",
        parameters={"type": "object", "properties": {}},
    )

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        fallback_text="fallback",
    )

    assert text == "Listo, evento creado."
    assert finish_reason == "stop"
    assert len(actions) == 1
    action = actions[0]
    assert action["id"] == "tc-abc"
    assert action["name"] == "calendar.create_event"
    assert action["arguments"] == {"title": "reunion"}
    assert action["result"] == {"status": "ok", "event_id": "ev-1"}
    assert len(fake.complete_calls) == 2


@pytest.mark.asyncio
async def test_qwen_2_vueltas_con_tool_call() -> None:
    """Qwen: vuelta 1 tool call, vuelta 2 otra tool call, vuelta 3 stop."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc1 = _make_tool_call("calendar.create_event", "tc-1")
    tc2 = _make_tool_call("calendar.create_event", "tc-2")

    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc1]))
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc2]))
    fake.queue_result(_make_result(text="Dos eventos creados.", finish_reason="stop"))

    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "ok"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea un evento",
        parameters={"type": "object", "properties": {}},
    )

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        fallback_text="fallback",
    )

    assert text == "Dos eventos creados."
    assert finish_reason == "stop"
    assert len(actions) == 2
    # Ambas actions tienen los 4 campos
    for i, (tc_id, _tc) in enumerate([("tc-1", tc1), ("tc-2", tc2)]):
        assert actions[i]["id"] == tc_id
        assert actions[i]["name"] == "calendar.create_event"
        assert actions[i]["arguments"] == {"title": "reunion"}
    assert len(fake.complete_calls) == 3


@pytest.mark.asyncio
async def test_guard_max_iteraciones_usa_fallback() -> None:
    """Al agotar MAX_TOOL_ITERATIONS, usa fallback_text si result.text esta vacio."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    # Siempre devuelve tool_calls sin converger (5 iteraciones + ninguna stop)
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))

    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "ok"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea un evento",
        parameters={"type": "object", "properties": {}},
    )

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        max_iterations=MAX_TOOL_ITERATIONS,
        fallback_text="no pude completar la tarea",
    )

    assert text == "no pude completar la tarea"
    # Guard agotado: finish_reason 'max_iterations' (sentinel honesto, no 'stop')
    assert finish_reason == "max_iterations"
    # 5 tool calls ejecutadas (una por iteracion)
    assert len(actions) == MAX_TOOL_ITERATIONS
    assert len(fake.complete_calls) == MAX_TOOL_ITERATIONS


@pytest.mark.asyncio
async def test_guard_max_iteraciones_usa_result_text_si_no_vacio() -> None:
    """Al agotar MAX_TOOL_ITERATIONS, usa result.text si NO esta vacio."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-y")
    # Las primeras N-1 iteraciones devuelven tool_calls con text vacio
    for _i in range(MAX_TOOL_ITERATIONS - 1):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La ultima iteracion tiene texto pero sigue en tool_calls (no converge)
    fake.queue_result(
        _make_result(text="algo parcial", finish_reason="tool_calls", tool_calls=[tc])
    )

    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "ok"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea un evento",
        parameters={"type": "object", "properties": {}},
    )

    text, _actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        max_iterations=MAX_TOOL_ITERATIONS,
        fallback_text="fallback no debe aparecer",
    )

    assert text == "algo parcial"
    # Guard agotado (aunque el ultimo result.text no este vacio).
    assert finish_reason == "max_iterations"


@pytest.mark.asyncio
async def test_unknown_tool_devuelve_tool_error() -> None:
    """Una tool call para un nombre desconocido devuelve tool_error en actions."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("nonexistent.tool", "tc-unk")
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    fake.queue_result(_make_result(text="No pude.", finish_reason="stop"))

    spec = ToolSpec(
        name="nonexistent.tool",
        description="no existe",
        parameters={"type": "object", "properties": {}},
    )

    _text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=_empty_registries(),
        fallback_text="fallback",
    )

    assert len(actions) == 1
    assert actions[0]["id"] == "tc-unk"
    assert actions[0]["name"] == "nonexistent.tool"
    assert actions[0]["arguments"] == {"title": "reunion"}
    result = actions[0]["result"]
    assert "error" in result
    assert result["error"]["code"] == "unknown_tool"
    assert finish_reason == "stop"


@pytest.mark.asyncio
async def test_degraded_termina_inmediatamente() -> None:
    """finish_reason='degraded' termina el loop sin ejecutar tools (aunque haya tool_calls)."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-deg")
    # Degraded con tool_calls: debe terminar sin ejecutar tools
    fake.queue_result(
        _make_result(
            text="lo siento, estoy degradado",
            finish_reason="degraded",
            tool_calls=[tc],
        )
    )

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        fallback_text="fallback",
    )

    assert text == "lo siento, estoy degradado"
    assert actions == []
    assert finish_reason == "degraded"
    assert len(fake.complete_calls) == 1


@pytest.mark.asyncio
async def test_result_text_vacio_final_usa_fallback() -> None:
    """Si result.text esta vacio al terminar, se usa fallback_text."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_make_result(text="", finish_reason="stop"))

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="gemma4",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        fallback_text="texto de fallback",
    )

    assert text == "texto de fallback"
    assert actions == []
    assert finish_reason == "stop"


@pytest.mark.asyncio
async def test_specs_vacia_pasa_tools_none() -> None:
    """Cuando specs=[], complete() debe recibir tools=None (Gemma conversacional)."""
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_make_result(text="ok", finish_reason="stop"))

    _text, _actions, _fr = await run_tool_loop(
        llm_client=fake,
        served_name="gemma4",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        fallback_text="fallback",
    )

    assert fake.complete_calls[0]["tools"] is None


@pytest.mark.asyncio
async def test_specs_no_vacia_pasa_tools_lista() -> None:
    """Cuando specs no esta vacia, complete() recibe la lista de ToolSpec."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_make_result(text="ok", finish_reason="stop"))

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea evento",
        parameters={"type": "object", "properties": {}},
    )

    _text, _actions, _fr = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=_empty_registries(),
        fallback_text="fallback",
    )

    assert fake.complete_calls[0]["tools"] == [spec]


# ---------------------------------------------------------------------------
# Tests de _execute_anywhere
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_anywhere_encuentra_en_default_registry() -> None:
    """_execute_anywhere usa el default registry si la tool esta ahi."""
    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "found_in_default"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    result = await _execute_anywhere("calendar.create_event", {}, (reg, None))
    assert result == {"status": "found_in_default"}


@pytest.mark.asyncio
async def test_execute_anywhere_encuentra_en_memory_registry() -> None:
    """_execute_anywhere usa el memory registry si la tool no esta en default."""
    default_reg = ToolRegistry()
    mem_reg = ToolRegistry()

    class MemTool:
        name = "memory.search"
        namespace = "memory"
        description = "busca en memoria"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "found_in_memory"}

    mem_reg.register(MemTool())  # type: ignore[arg-type]

    result = await _execute_anywhere("memory.search", {}, (default_reg, mem_reg))
    assert result == {"status": "found_in_memory"}


@pytest.mark.asyncio
async def test_execute_anywhere_tool_desconocida() -> None:
    """_execute_anywhere devuelve tool_error si ninguna registry tiene la tool."""
    result = await _execute_anywhere("nowhere.tool", {}, _empty_registries())
    assert "error" in result
    assert result["error"]["code"] == "unknown_tool"


# ---------------------------------------------------------------------------
# Tests: tool_call_id + name en ChatMessage de tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chatmessage_tool_contiene_id_y_nombre() -> None:
    """El ChatMessage 'tool' incluye tool_call_id y name correctos."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = ToolCall(id="mi-id", name="calendar.create_event", arguments={})
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    fake.queue_result(_make_result(text="listo", finish_reason="stop"))

    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"status": "ok"}

    reg.register(FakeTool())  # type: ignore[arg-type]

    msgs = _messages()
    _text, _actions, _fr = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=msgs,
        specs=[],
        registries=(reg, None),
        fallback_text="fallback",
    )

    # Debe haber un mensaje de tool en el historial
    tool_msgs = [m for m in msgs if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "mi-id"
    assert tool_msgs[0].name == "calendar.create_event"
    # El content debe ser JSON del resultado
    content_dict = json.loads(tool_msgs[0].content)  # type: ignore[arg-type]
    assert content_dict == {"status": "ok"}


# ---------------------------------------------------------------------------
# Tests: ToolRegistry.has()
# ---------------------------------------------------------------------------


def test_registry_has_tool_registrada() -> None:
    """has() devuelve True para una tool registrada."""
    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {}

    reg.register(FakeTool())  # type: ignore[arg-type]
    assert reg.has("calendar.create_event") is True


def test_registry_has_tool_no_registrada() -> None:
    """has() devuelve False para un nombre que no existe."""
    reg = ToolRegistry()
    assert reg.has("nonexistent.tool") is False


def test_registry_has_en_registry_vacio() -> None:
    """has() devuelve False en un registry vacio."""
    reg = ToolRegistry()
    assert reg.has("cualquier.cosa") is False
