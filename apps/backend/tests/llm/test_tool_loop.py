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
from app.llm.errors import LlmTimeoutError
from app.llm.schemas import (
    ChatMessage,
    CompletionResult,
    ToolCall,
    ToolSpec,
)
from app.llm.tool_loop import (
    MAX_CALLS_PER_TURN,
    MAX_TOOL_ITERATIONS,
    _execute_anywhere,
    run_tool_loop,
)
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
async def test_tool_call_luego_stop_vacio_fuerza_confirmacion() -> None:
    """Gotcha qwen real (medido en E2E): tras EJECUTAR una tool, el modelo corta con
    finish_reason terminal ('stop') y content VACIO. El loop NO debe devolver el
    fallback generico (lee como error aunque la accion SI ocurrio): fuerza UNA completion
    final SIN tools para que el modelo confirme lo accionado. El finish_reason real de la
    forzada reemplaza al terminal-vacio."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    # 1) tool call (no terminal) -> se ejecuta la tool
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # 2) corte terminal 'stop' con content VACIO (el gotcha)
    fake.queue_result(_make_result(text="", finish_reason="stop"))
    # 3) completion forzada SIN tools: el modelo confirma en lenguaje natural
    fake.queue_result(_make_result(text="Listo, te agende Gimnasio.", finish_reason="stop"))

    reg = ToolRegistry()

    class FakeTool:
        name = "calendar.create_event"
        namespace = "calendar"
        description = "crea un evento"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> dict:
            return {"id": "ev-9", "status": "confirmed"}

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
        fallback_text="FALLBACK-no-deberia-verse",
    )

    # La accion se ejecuto y NO se cae al fallback: el usuario ve la confirmacion forzada.
    assert text == "Listo, te agende Gimnasio."
    assert finish_reason == "stop"
    assert len(actions) == 1
    assert actions[0]["result"] == {"id": "ev-9", "status": "confirmed"}
    # 3 llamadas: tool_call + stop-vacio + forzada-sin-tools.
    assert len(fake.complete_calls) == 3
    # La 3ra (forzada) va SIN tools.
    assert fake.complete_calls[2]["tools"] is None


@pytest.mark.asyncio
async def test_stop_vacio_sin_acciones_no_fuerza_y_cae_a_fallback() -> None:
    """Sin acciones ejecutadas, una respuesta normal vacia NO dispara la forzada: cae al
    fallback (no se gasta una inferencia extra en un turno conversacional legitimo vacio).
    El gate de la forzada es ``actions``, no ``not last_text`` a secas."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_make_result(text="", finish_reason="stop"))

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        fallback_text="fallback",
    )

    assert text == "fallback"
    assert actions == []
    assert finish_reason == "stop"
    assert len(fake.complete_calls) == 1  # NO hay forzada


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


def _looping_registry_and_spec() -> tuple[ToolRegistry, ToolSpec]:
    """Registry + spec de una tool fake que siempre devuelve ok (para tests de loop)."""
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
    return reg, spec


@pytest.mark.asyncio
async def test_guard_max_iteraciones_fuerza_respuesta_final() -> None:
    """Al agotar MAX_TOOL_ITERATIONS con texto vacío, una completion final SIN tools.

    Regresión (#260): un modelo que loopea llamando tools (p.ej. qwen reintentando el
    stub memory.add) agotaba las iteraciones sin dar un texto final -> el usuario veía
    el ``fallback_text`` ("no pude procesar...") AUNQUE las tools sí se ejecutaron. Ahora
    se fuerza UNA completion sin tools: sin tools que llamar, el modelo responde en
    lenguaje natural y el usuario ve una respuesta real (no el fallback)."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    # Las MAX iteraciones devuelven tool_calls con texto vacío (nunca converge).
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La completion FORZADA (sin tools) devuelve la respuesta final real.
    fake.queue_result(_make_result(text="Listo, lo anoté en tu memoria.", finish_reason="stop"))

    reg, spec = _looping_registry_and_spec()

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        max_iterations=MAX_TOOL_ITERATIONS,
        fallback_text="no pude completar la tarea",
    )

    # NO el fallback: la completion forzada produjo una respuesta real.
    assert text == "Listo, lo anoté en tu memoria."
    # La completion forzada devolvió texto con finish_reason "stop": se usa ese
    # finish_reason real, no el sentinel "max_iterations" (FIX 3 — telemetría honesta).
    assert finish_reason == "stop"
    # 5 tool calls ejecutadas en el loop + 1 completion forzada al final = 6 complete().
    assert len(actions) == MAX_TOOL_ITERATIONS
    assert len(fake.complete_calls) == MAX_TOOL_ITERATIONS + 1
    # La completion FORZADA va SIN tools (para que el modelo responda, no tool-callee).
    assert fake.complete_calls[-1]["tools"] is None


@pytest.mark.asyncio
async def test_guard_max_iteraciones_usa_fallback_si_forzada_vacia() -> None:
    """Si la completion final forzada TAMBIÉN vuelve vacía, se cae al fallback_text."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La completion forzada también vuelve vacía -> fallback (sin empeorar el caso previo).
    fake.queue_result(_make_result(text="", finish_reason="stop"))

    reg, spec = _looping_registry_and_spec()

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
    assert finish_reason == "max_iterations"
    assert len(actions) == MAX_TOOL_ITERATIONS
    assert len(fake.complete_calls) == MAX_TOOL_ITERATIONS + 1
    assert fake.complete_calls[-1]["tools"] is None


@pytest.mark.asyncio
async def test_guard_max_iteraciones_completion_forzada_propaga_error() -> None:
    """Si la completion final forzada tira ``LlmError``, propaga al caller.

    No se envuelve en try/except acá (igual que las completions del loop): ``route()``
    captura la familia ``LlmError`` y degrada. Este test fija que el error NO se traga
    silenciosamente dentro de ``run_tool_loop``."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La completion forzada (6ta) falla -> debe propagar.
    fake.queue_error(LlmTimeoutError("timeout"))

    reg, spec = _looping_registry_and_spec()

    with pytest.raises(LlmTimeoutError):
        await run_tool_loop(
            llm_client=fake,
            served_name="qwen",
            messages=_messages(),
            specs=[spec],
            registries=(reg, None),
            max_iterations=MAX_TOOL_ITERATIONS,
            fallback_text="no pude completar la tarea",
        )


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
async def test_cap_tool_calls_por_turno() -> None:
    """Si el modelo emite mas de MAX_CALLS_PER_TURN, solo se ejecutan cap."""
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    extra = 3
    many = [
        _make_tool_call("calendar.create_event", f"tc-{i}")
        for i in range(MAX_CALLS_PER_TURN + extra)
    ]
    # Turno 1: el modelo emite cap+extra tool_calls. Turno 2: stop.
    fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=many))
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

    spec = ToolSpec(
        name="calendar.create_event",
        description="crea un evento",
        parameters={"type": "object", "properties": {}},
    )

    msgs = _messages()
    _text, actions, _fr = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=msgs,
        specs=[spec],
        registries=(reg, None),
        fallback_text="fallback",
    )

    # Solo se ejecutan las primeras cap, en orden; las extra se descartan.
    assert len(actions) == MAX_CALLS_PER_TURN
    assert [a["id"] for a in actions] == [f"tc-{i}" for i in range(MAX_CALLS_PER_TURN)]

    # El assistant message del historial preserva SOLO las calls ejecutadas
    # (correlacion assistant/tool consistente para el parser hermes).
    assistant_msgs = [m for m in msgs if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].tool_calls is not None
    assert len(assistant_msgs[0].tool_calls) == MAX_CALLS_PER_TURN
    # Hay un ChatMessage 'tool' por cada call ejecutada, no por las extra.
    tool_msgs = [m for m in msgs if m.role == "tool"]
    assert len(tool_msgs) == MAX_CALLS_PER_TURN


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
# Tests: passthrough de thinking por rol (ADR-012 D4, #205)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("thinking", [True, False, None])
async def test_run_tool_loop_pasa_thinking_a_complete(thinking: bool | None) -> None:
    """``run_tool_loop(thinking=...)`` hila el flag tal cual a ``complete``.

    El thinking es passthrough puro hacia ``llm_client.complete`` (lo decide el
    router por rol): True/False fuerzan ON/OFF, None deja el default del server.
    """
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(_make_result(text="ok", finish_reason="stop"))

    _text, _actions, _fr = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[],
        registries=_empty_registries(),
        thinking=thinking,
        fallback_text="fallback",
    )

    # Identidad estricta: el flag debe llegar sin reinterpretarse (None != False).
    assert fake.complete_calls[0]["thinking"] is thinking


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


# ---------------------------------------------------------------------------
# Tests: FIX 3 — finish_reason de la completion forzada
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_forzada_con_texto_usa_finish_reason_real() -> None:
    """La completion forzada con texto usa su finish_reason real, no 'max_iterations'.

    FIX 3 (telemetria): cuando el guard se agota y la completion forzada (tools=None)
    produce texto, el finish_reason retornado es el de esa completion (p.ej. 'stop' o
    'length'). El sentinel 'max_iterations' se reserva para cuando la forzada TAMBIEN
    vuelve vacia (sin texto util).
    """
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La completion forzada devuelve texto con finish_reason "length" (truncado).
    fake.queue_result(_make_result(text="Respuesta truncada.", finish_reason="length"))

    reg, spec = _looping_registry_and_spec()

    text, actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        max_iterations=MAX_TOOL_ITERATIONS,
        fallback_text="no pude completar la tarea",
    )

    assert text == "Respuesta truncada."
    # finish_reason de la forzada, no el sentinel (FIX 3).
    assert finish_reason == "length"
    assert len(actions) == MAX_TOOL_ITERATIONS
    assert len(fake.complete_calls) == MAX_TOOL_ITERATIONS + 1


@pytest.mark.asyncio
async def test_guard_forzada_vacia_mantiene_sentinel_max_iterations() -> None:
    """Si la completion forzada vuelve vacia, finish_reason sigue siendo 'max_iterations'.

    Complemento del test anterior: cuando la forzada no produce texto (cae al
    fallback_text), el sentinel 'max_iterations' se preserva intacto.
    """
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))

    tc = _make_tool_call("calendar.create_event", "tc-x")
    for _i in range(MAX_TOOL_ITERATIONS):
        fake.queue_result(_make_result(text="", finish_reason="tool_calls", tool_calls=[tc]))
    # La completion forzada vuelve vacia -> sentinel se mantiene.
    fake.queue_result(_make_result(text="", finish_reason="stop"))

    reg, spec = _looping_registry_and_spec()

    text, _actions, finish_reason = await run_tool_loop(
        llm_client=fake,
        served_name="qwen",
        messages=_messages(),
        specs=[spec],
        registries=(reg, None),
        max_iterations=MAX_TOOL_ITERATIONS,
        fallback_text="fallback sentinel",
    )

    assert text == "fallback sentinel"
    # Forzada vacia: el sentinel 'max_iterations' se preserva (FIX 3).
    assert finish_reason == "max_iterations"
    assert len(fake.complete_calls) == MAX_TOOL_ITERATIONS + 1
