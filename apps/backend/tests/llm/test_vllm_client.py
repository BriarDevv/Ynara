"""Contract tests del ``VllmClient`` con ``httpx.MockTransport`` (M2).

``MockTransport`` es nativo de httpx (no necesita ``respx``): inyectamos
un ``httpx.AsyncClient`` con un handler que devuelve respuestas grabadas
del shape OpenAI de vLLM. Cubrimos: complete con texto, complete con
tool_calls, mapeo de cada error HTTP, timeout / connect, streaming y
health.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.llm.clients.parsers import OpenAIToolCallParser
from app.llm.clients.vllm import VllmClient
from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelNotServedError,
    ToolParsingError,
)
from app.llm.schemas import ChatMessage, ToolCall, ToolSpec

_FIXTURES = Path(__file__).parent / "fixtures"
_BASE_URL = "http://vllm-test:8001/v1"
_MODEL = "qwen-3.5-9b"


def _load(name: str) -> Any:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _client(handler: Any) -> VllmClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return VllmClient(
        base_url=_BASE_URL,
        served_models=frozenset({_MODEL}),
        http_client=http,
        parser=OpenAIToolCallParser(),
    )


def _ollama_client(handler: Any) -> VllmClient:
    """Cliente con ``engine="ollama"``: rutea por la API nativa ``/api/chat`` (ADR-014 D4)."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return VllmClient(
        base_url=_BASE_URL,
        served_models=frozenset({_MODEL}),
        http_client=http,
        parser=OpenAIToolCallParser(),
        engine="ollama",
    )


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="hola")]


# ---------- serves_model / model gating ----------


@pytest.mark.asyncio
async def test_serves_model() -> None:
    client = _client(lambda req: httpx.Response(200, json={}))
    assert client.serves_model(_MODEL)
    assert not client.serves_model("otro-modelo")


@pytest.mark.asyncio
async def test_complete_unknown_model_raises() -> None:
    client = _client(lambda req: httpx.Response(200, json={}))
    with pytest.raises(ModelNotServedError):
        await client.complete(model="no-servido", messages=_messages())


# ---------- complete OK ----------


@pytest.mark.asyncio
async def test_complete_text() -> None:
    body = _load("completion_text.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == _MODEL
        assert payload["stream"] is False
        assert "tools" not in payload
        return httpx.Response(200, json=body)

    client = _client(handler)
    result = await client.complete(model=_MODEL, messages=_messages())
    assert result.text == "Hola, en que te puedo ayudar?"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"
    assert result.prompt_tokens == 18
    assert result.completion_tokens == 9
    assert result.model_name == _MODEL
    assert result.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_complete_with_tools_in_payload() -> None:
    body = _load("completion_tool_call.json")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tool_choice"] == "auto"
        assert payload["tools"][0]["function"]["name"] == "get_weather"
        return httpx.Response(200, json=body)

    client = _client(handler)
    tools = [
        ToolSpec(
            name="get_weather",
            description="clima",
            parameters={"type": "object", "properties": {}},
        )
    ]
    result = await client.complete(model=_MODEL, messages=_messages(), tools=tools)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == {
        "city": "Buenos Aires",
        "units": "celsius",
    }
    assert result.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_complete_encodes_assistant_tool_calls_in_payload() -> None:
    """Un assistant con ``tool_calls`` se re-serializa al wire OpenAI (multi-turno con tool).

    Regresion (#256): ``_encode_message`` dropeaba ``message.tool_calls``, asi que la
    2da vuelta del tool loop mandaba un assistant ``content:null`` SIN tool_calls. Ollama
    rechaza eso con 400 ("invalid message content type: <nil>") -> el turno degradaba y la
    consolidacion de memoria no corria. El assistant que llamo una tool DEBE re-enviarse con
    sus ``tool_calls`` (formato OpenAI: ``arguments`` como JSON string) para correlacionar con
    el mensaje ``role='tool'`` siguiente.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_load("completion_text.json"))

    client = _client(handler)
    messages = [
        ChatMessage(role="system", content="sos un asistente"),
        ChatMessage(role="user", content="recordame algo"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="crear_recordatorio",
                    arguments={"titulo": "x", "fecha_hora": "2026-06-16T09:00:00"},
                )
            ],
        ),
        ChatMessage(
            role="tool",
            tool_call_id="call_1",
            name="crear_recordatorio",
            content='{"ok": true}',
        ),
    ]
    await client.complete(model=_MODEL, messages=messages)

    wire = captured["payload"]["messages"]
    # Un mensaje normal (sin tool_calls) NO debe traer la clave (no ensuciar el wire).
    assert "tool_calls" not in wire[0]
    # El assistant que llamo la tool DEBE traer tool_calls en formato OpenAI.
    assistant = wire[2]
    assert assistant["role"] == "assistant"
    # ``content:null`` ES valido cuando van los tool_calls (el otro lado del bug del 400).
    assert assistant.get("content") is None
    assert "tool_calls" in assistant, "el assistant re-envia sus tool_calls (sino Ollama 400)"
    tc = assistant["tool_calls"][0]
    assert tc["id"] == "call_1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "crear_recordatorio"
    # ``arguments`` viaja como JSON string (wire OpenAI), no como dict.
    assert json.loads(tc["function"]["arguments"]) == {
        "titulo": "x",
        "fecha_hora": "2026-06-16T09:00:00",
    }
    # El mensaje role='tool' siguiente conserva su correlacion con la call.
    assert wire[3]["role"] == "tool"
    assert wire[3]["tool_call_id"] == "call_1"


@pytest.mark.asyncio
async def test_complete_omits_empty_tool_calls_from_payload() -> None:
    """Un assistant con ``tool_calls=[]`` NO emite la clave en el wire (truthy check).

    Un ``"tool_calls": []`` junto a ``content:null`` seria tan invalido para Ollama
    como omitir la clave; el encode usa truthy check (no ``is not None``), asi que una
    lista vacia no ensucia el payload. Hoy el tool_loop nunca construye ese mensaje,
    pero el test sella la rama defensiva.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_load("completion_text.json"))

    client = _client(handler)
    messages = [
        ChatMessage(role="user", content="hola"),
        ChatMessage(role="assistant", content="respuesta sin tools", tool_calls=[]),
    ]
    await client.complete(model=_MODEL, messages=messages)
    assert "tool_calls" not in captured["payload"]["messages"][1]


@pytest.mark.asyncio
async def test_complete_propagates_tool_parsing_error() -> None:
    # arguments malformado en la respuesta -> ToolParsingError sale por complete().
    body = _load("completion_bad_arguments.json")
    client = _client(lambda req: httpx.Response(200, json=body))
    with pytest.raises(ToolParsingError):
        await client.complete(model=_MODEL, messages=_messages())


# ---------- thinking por rol (camino vLLM): reasoning_effort + chat_template_kwargs ----------
# Estos tests cubren el camino OpenAI-compat (engine="vllm", default, #205): reasoning_effort
# lo honra vLLM (y qwen via Ollama por su canal reasoning) + chat_template_kwargs cubre vLLM
# sin reasoning-parser. El control de thinking de gemma4 en Ollama va por la API nativa
# /api/chat (engine="ollama"), cubierto en la sección "Ollama engine" más abajo (ADR-014 D4).


@pytest.mark.asyncio
async def test_complete_thinking_false_sets_enable_thinking_false() -> None:
    """``thinking=False`` -> payload trae ``chat_template_kwargs.enable_thinking`` False.

    Garantiza el OFF explicito del conversacional (Gemma): con thinking activo
    devuelve content vacio (gotcha medido); el False explicito pisa el default.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_load("completion_text.json"))

    client = _client(handler)
    await client.complete(model=_MODEL, messages=_messages(), thinking=False)
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is False
    # reasoning_effort: el param que honra Ollama (none = thinking OFF)
    assert captured["payload"]["reasoning_effort"] == "none"


@pytest.mark.asyncio
async def test_complete_thinking_true_sets_enable_thinking_true() -> None:
    """``thinking=True`` -> payload trae ``chat_template_kwargs.enable_thinking`` True.

    El agente (Qwen) piensa para planificar tool calls; el True explicito asegura
    ON aunque cambie el default del server.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_load("completion_text.json"))

    client = _client(handler)
    await client.complete(model=_MODEL, messages=_messages(), thinking=True)
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is True
    # reasoning_effort: el param que honra Ollama (medium = thinking ON)
    assert captured["payload"]["reasoning_effort"] == "medium"


@pytest.mark.asyncio
async def test_complete_thinking_none_omits_chat_template_kwargs() -> None:
    """Sin ``thinking`` (default None) -> NO se emite ``chat_template_kwargs``.

    Preserva el comportamiento previo exacto: la clave no aparece y el server usa
    su default.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_load("completion_text.json"))

    client = _client(handler)
    await client.complete(model=_MODEL, messages=_messages())
    assert "chat_template_kwargs" not in captured["payload"]
    assert "reasoning_effort" not in captured["payload"]


@pytest.mark.asyncio
async def test_stream_thinking_false_sets_enable_thinking_false() -> None:
    """``stream`` tambien hila ``thinking``: OFF -> ``enable_thinking`` False en payload.

    Cubre la rama de stream para que el flag no quede sin tocar en streaming.
    """
    sse = (_FIXTURES / "stream_text.sse").read_text(encoding="utf-8")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, content=sse.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    async for _ in client.stream(model=_MODEL, messages=_messages(), thinking=False):
        pass
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is False
    # reasoning_effort: el param que honra Ollama (none = thinking OFF)
    assert captured["payload"]["reasoning_effort"] == "none"


@pytest.mark.asyncio
async def test_stream_thinking_true_sets_enable_thinking_true() -> None:
    """``stream(thinking=True)`` -> ``enable_thinking`` True en el payload.

    Simetria ON con ``complete``: el agente (Qwen) piensa para planificar tool
    calls tambien en streaming; el True explicito asegura ON aunque cambie el
    default del server.
    """
    sse = (_FIXTURES / "stream_text.sse").read_text(encoding="utf-8")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, content=sse.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    async for _ in client.stream(model=_MODEL, messages=_messages(), thinking=True):
        pass
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is True
    # reasoning_effort: el param que honra Ollama (medium = thinking ON)
    assert captured["payload"]["reasoning_effort"] == "medium"


@pytest.mark.asyncio
async def test_stream_thinking_none_omits_chat_template_kwargs() -> None:
    """Sin ``thinking`` (default None) en ``stream`` -> NO se emite ``chat_template_kwargs``.

    Simetria None con ``complete``: la clave no aparece y el server usa su default
    tambien por la rama de streaming.
    """
    sse = (_FIXTURES / "stream_text.sse").read_text(encoding="utf-8")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, content=sse.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    async for _ in client.stream(model=_MODEL, messages=_messages()):
        pass
    assert "chat_template_kwargs" not in captured["payload"]
    assert "reasoning_effort" not in captured["payload"]


# ---------- Ollama engine: ruteo por la API nativa /api/chat (ADR-014 D4) ----------
# Con engine="ollama" el cliente NO usa el OpenAI-compat (que ignora el thinking de
# gemma4, upstream Ollama #15288/#15293/#15635): rutea por la API nativa /api/chat con el
# top-level `think`. Estos tests usan MockTransport y afirman la FORMA del request nativo +
# el parseo de la respuesta nativa (content/thinking/tool_calls/streaming).


def _native_done_body(
    *, content: str = "ok", thinking: str = "", done_reason: str = "stop"
) -> dict[str, Any]:
    """Respuesta nativa no-stream mínima de Ollama (``/api/chat`` con ``done:true``)."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if thinking:
        message["thinking"] = thinking
    return {
        "model": "gemma4",
        "message": message,
        "done": True,
        "done_reason": done_reason,
        "prompt_eval_count": 12,
        "eval_count": 5,
    }


@pytest.mark.asyncio
async def test_ollama_complete_routes_to_native_api_chat_with_think_false() -> None:
    """``engine="ollama"`` + ``thinking=False`` -> POST a ``/api/chat`` con ``think:false``.

    El fix del gotcha de gemma4: el control de thinking va por la API nativa, NO por el
    OpenAI-compat (que lo ignora). Las claves OpenAI de thinking NUNCA viajan por acá.
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_native_done_body(content="Hola"))

    client = _ollama_client(handler)
    result = await client.complete(model=_MODEL, messages=_messages(), thinking=False)

    # Ruteo: el /v1 del base_url se cae; el request va a la API nativa.
    assert captured["path"] == "/api/chat"
    payload = captured["payload"]
    assert payload["think"] is False
    assert payload["stream"] is False
    # Las claves del OpenAI-compat NO se filtran al camino nativo.
    assert "chat_template_kwargs" not in payload
    assert "reasoning_effort" not in payload
    # El sampling va en ``options`` (num_predict = max_tokens nativo).
    assert payload["options"]["num_predict"] == 1024
    assert payload["options"]["temperature"] == 0.7
    # Parseo de la respuesta nativa.
    assert result.text == "Hola"
    assert result.finish_reason == "stop"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 5
    assert result.model_name == "gemma4"


@pytest.mark.asyncio
async def test_ollama_complete_think_true() -> None:
    """``engine="ollama"`` sin tools + ``thinking=True`` -> ``think:true`` en el body nativo."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_native_done_body())

    client = _ollama_client(handler)
    await client.complete(model=_MODEL, messages=_messages(), thinking=True)
    assert captured["payload"]["think"] is True


@pytest.mark.asyncio
async def test_ollama_complete_thinking_none_omits_think() -> None:
    """Sin ``thinking`` (None) -> NO se emite ``think`` (usa el default del modelo)."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_native_done_body())

    client = _ollama_client(handler)
    await client.complete(model=_MODEL, messages=_messages())
    assert "think" not in captured["payload"]


@pytest.mark.asyncio
async def test_ollama_complete_maps_thinking_channel_to_reasoning() -> None:
    """La respuesta nativa mapea ``message.thinking`` -> ``CompletionResult.reasoning``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_native_done_body(content="respuesta", thinking="razonando...")
        )

    client = _ollama_client(handler)
    result = await client.complete(model=_MODEL, messages=_messages(), thinking=True)
    assert result.text == "respuesta"
    assert result.reasoning == "razonando..."


@pytest.mark.asyncio
async def test_ollama_with_tools_routes_to_openai_compat() -> None:
    """``engine="ollama"`` + tools presentes -> camino OpenAI-compat (NO nativo).

    El agent-loop de qwen (productividad/memoria) requiere tool-calling que funciona
    correctamente en el OpenAI-compat de Ollama. Rutear por el nativo rompe el loop:
    el streaming nativo emite tool_calls completas (incompatible con el accumulator de
    deltas del agente, ADR-021/022). Solo los requests SIN tools van por el nativo
    (gemma4 conversacional, thinking off). El thinking con tools va por
    ``reasoning_effort`` (qwen sí lo honra en el OpenAI-compat).
    """
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        # Respuesta en formato OpenAI-compat (no nativa).
        body = {
            "id": "chatcmpl-1",
            "model": _MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Rosario"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        return httpx.Response(200, json=body)

    client = _ollama_client(handler)
    tools = [
        ToolSpec(
            name="get_weather",
            description="clima",
            parameters={"type": "object", "properties": {}},
        )
    ]
    result = await client.complete(model=_MODEL, messages=_messages(), tools=tools, thinking=True)
    # Con tools -> camino OpenAI-compat (/v1/chat/completions), no el nativo.
    assert captured["path"] == "/v1/chat/completions"
    # El control de thinking NO va por ``think`` (nativo), sino por reasoning_effort.
    assert "think" not in captured["payload"]
    assert captured["payload"]["reasoning_effort"] == "medium"
    # Tools y tool_choice en el wire OpenAI.
    assert captured["payload"]["tool_choice"] == "auto"
    assert captured["payload"]["tools"][0]["function"]["name"] == "get_weather"
    # Parseo correcto de la respuesta OpenAI.
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == {"city": "Rosario"}
    assert result.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_ollama_complete_encodes_native_messages() -> None:
    """El wire nativo: ``content:null`` -> ``""`` y tool_calls con ``arguments`` como dict."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_native_done_body())

    client = _ollama_client(handler)
    messages = [
        ChatMessage(role="user", content="recordame algo"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="call_1", name="crear_recordatorio", arguments={"titulo": "x"})
            ],
        ),
        ChatMessage(
            role="tool", tool_call_id="call_1", name="crear_recordatorio", content='{"ok": true}'
        ),
    ]
    await client.complete(model=_MODEL, messages=messages, thinking=True)
    wire = captured["payload"]["messages"]
    # content:null -> "" (la API nativa no acepta null).
    assert wire[1]["content"] == ""
    # tool_calls nativas: arguments como objeto (dict), NO JSON string.
    assert wire[1]["tool_calls"][0]["function"]["arguments"] == {"titulo": "x"}
    # el rol tool lleva tool_name (nativo).
    assert wire[2]["role"] == "tool"
    assert wire[2]["tool_name"] == "crear_recordatorio"


@pytest.mark.asyncio
async def test_ollama_stream_native_ndjson_content_and_thinking() -> None:
    """El streaming nativo (NDJSON) acumula ``message.content`` + ``message.thinking`` y cierra."""
    events: list[dict[str, Any]] = [
        {"message": {"role": "assistant", "content": "", "thinking": "pien"}, "done": False},
        {"message": {"role": "assistant", "content": "Hola", "thinking": ""}, "done": False},
        {"message": {"role": "assistant", "content": " mundo"}, "done": False},
        {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop"},
    ]
    lines = "".join(json.dumps(event) + "\n" for event in events)
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, content=lines.encode("utf-8"), headers={"content-type": "application/x-ndjson"}
        )

    client = _ollama_client(handler)
    chunks = [
        chunk async for chunk in client.stream(model=_MODEL, messages=_messages(), thinking=False)
    ]
    assert captured["path"] == "/api/chat"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["think"] is False
    texts = "".join(c.delta_text for c in chunks if c.delta_text)
    assert texts == "Hola mundo"
    reasoning = "".join(c.reasoning_delta for c in chunks if c.reasoning_delta)
    assert reasoning == "pien"
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_ollama_complete_http_error_mapped() -> None:
    """El camino nativo reusa el mapeo de errores HTTP (503 -> LlmUnavailableError)."""
    client = _ollama_client(lambda req: httpx.Response(503, json={"error": "x"}))
    with pytest.raises(LlmUnavailableError):
        await client.complete(model=_MODEL, messages=_messages(), thinking=False)


@pytest.mark.asyncio
async def test_ollama_stream_timeout_mapped() -> None:
    """El streaming nativo mapea timeout a ``LlmTimeoutError`` (igual que el camino vLLM)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _ollama_client(handler)
    with pytest.raises(LlmTimeoutError):
        async for _ in client.stream(model=_MODEL, messages=_messages(), thinking=False):
            pass


# ---------- smoke contra Ollama real (opt-in, ADR-014 D4) ----------


@pytest.mark.llm_smoke
@pytest.mark.skipif(
    not os.getenv("YNARA_OLLAMA_SMOKE"),
    reason="smoke contra Ollama real: setear YNARA_OLLAMA_SMOKE=1 (con gemma4 en :11434)",
)
@pytest.mark.asyncio
async def test_ollama_smoke_gemma4_thinking_off_returns_content() -> None:
    """Smoke (opt-in) contra un Ollama REAL: gemma4 con thinking OFF responde con content.

    Reproduce el gotcha y prueba el fix end-to-end: sin el ruteo nativo /api/chat con
    ``think:false``, gemma4 devuelve ``content:""`` + ``finish_reason:"length"`` (todo en
    reasoning). Con el fix, ``content`` NO está vacío y ``finish_reason != "length"``.

    Opt-in: corre solo con ``YNARA_OLLAMA_SMOKE=1`` (skippeado por defecto, sin red en CI).
    Config por env: ``YNARA_OLLAMA_BASE_URL`` (default http://localhost:11434/v1),
    ``YNARA_OLLAMA_GEMMA_MODEL`` (default ``gemma4``).
    """
    base_url = os.getenv("YNARA_OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = os.getenv("YNARA_OLLAMA_GEMMA_MODEL", "gemma4")
    client = VllmClient(
        base_url=base_url,
        served_models=frozenset({model}),
        http_client=httpx.AsyncClient(),
        parser=OpenAIToolCallParser(),
        engine="ollama",
        default_timeout_s=120.0,
    )
    try:
        result = await client.complete(
            model=model,
            messages=[ChatMessage(role="user", content="Decime hola en una sola palabra.")],
            thinking=False,
            max_tokens=64,
        )
    finally:
        await client.aclose()
    assert result.text.strip() != "", "gemma4 con thinking OFF debe devolver content NO vacío"
    assert result.finish_reason != "length", (
        "content vacío + finish_reason='length' = el thinking no se apagó (regresión del gotcha)"
    )


# ---------- timeout configurable (#27) ----------


@pytest.mark.asyncio
async def test_complete_uses_configured_default_timeout() -> None:
    # Sin timeout_s explicito el cliente usa default_timeout_s; el router M8
    # lo construye con config.serving.request_timeout_s.
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json=_load("completion_text.json"))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = VllmClient(
        base_url=_BASE_URL,
        served_models=frozenset({_MODEL}),
        http_client=http,
        parser=OpenAIToolCallParser(),
        default_timeout_s=120.0,
    )
    await client.complete(model=_MODEL, messages=_messages())
    assert captured["timeout"]["read"] == 120.0


@pytest.mark.asyncio
async def test_complete_explicit_timeout_overrides_default() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json=_load("completion_text.json"))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = VllmClient(
        base_url=_BASE_URL,
        served_models=frozenset({_MODEL}),
        http_client=http,
        parser=OpenAIToolCallParser(),
        default_timeout_s=120.0,
    )
    await client.complete(model=_MODEL, messages=_messages(), timeout_s=5.0)
    assert captured["timeout"]["read"] == 5.0


# ---------- mapeo de errores HTTP ----------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, LlmOverloadedError),
        (400, LlmBadRequestError),
        (422, LlmBadRequestError),
        (503, LlmUnavailableError),
        (500, LlmUnavailableError),
    ],
)
async def test_complete_http_error_mapping(status: int, expected: type[Exception]) -> None:
    client = _client(lambda req: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(expected):
        await client.complete(model=_MODEL, messages=_messages())


# ---------- 400 overflow -> LlmContextOverflowError (P2.4) ----------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overflow_msg",
    [
        "This model's maximum context length is 8192 tokens, however you requested 9000.",
        "The input exceeds the context length of the model.",
        "Please reduce the length of the messages.",
        "MAXIMUM CONTEXT LENGTH exceeded",  # case-insensitive
    ],
)
async def test_complete_400_overflow_maps_to_context_overflow(overflow_msg: str) -> None:
    body = {"error": {"message": overflow_msg, "type": "BadRequestError"}}
    client = _client(lambda req: httpx.Response(400, json=body))
    with pytest.raises(LlmContextOverflowError):
        await client.complete(model=_MODEL, messages=_messages())


@pytest.mark.asyncio
async def test_complete_400_generic_stays_bad_request() -> None:
    # Un 400 sin firma de overflow sigue siendo LlmBadRequestError plano y NO
    # la subclase de overflow.
    body = {"error": {"message": "invalid value for parameter 'temperature'"}}
    client = _client(lambda req: httpx.Response(400, json=body))
    with pytest.raises(LlmBadRequestError) as excinfo:
        await client.complete(model=_MODEL, messages=_messages())
    assert not isinstance(excinfo.value, LlmContextOverflowError)


@pytest.mark.asyncio
async def test_complete_overflow_detail_does_not_leak_body() -> None:
    # Regla #4: el detail de la excepcion es una etiqueta fija (status), nunca
    # el body crudo del request del usuario.
    leaky = "your prompt 'mi secreto 4111-1111' exceeds the maximum context length"
    client = _client(lambda req: httpx.Response(400, json={"error": {"message": leaky}}))
    with pytest.raises(LlmContextOverflowError) as excinfo:
        await client.complete(model=_MODEL, messages=_messages())
    rendered = str(excinfo.value)
    assert "mi secreto" not in rendered
    assert "4111-1111" not in rendered
    assert rendered == "contexto excedido: HTTP 400"


@pytest.mark.asyncio
async def test_complete_422_overflow_signature_stays_bad_request() -> None:
    # La deteccion de overflow es solo para 400 (no 422): un 422 con la firma
    # sigue siendo LlmBadRequestError plano.
    body = {"error": {"message": "maximum context length"}}
    client = _client(lambda req: httpx.Response(422, json=body))
    with pytest.raises(LlmBadRequestError) as excinfo:
        await client.complete(model=_MODEL, messages=_messages())
    assert not isinstance(excinfo.value, LlmContextOverflowError)


# ---------- asimetría intencional: stream() NO mapea 400-overflow ----------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overflow_msg",
    [
        "This model's maximum context length is 8192 tokens, however you requested 9000.",
        "The input exceeds the context length of the model.",
        "Please reduce the length of the messages.",
    ],
)
async def test_stream_400_overflow_stays_bad_request(overflow_msg: str) -> None:
    """``stream()`` con un 400 + firma de overflow levanta ``LlmBadRequestError`` PLANO,
    NO ``LlmContextOverflowError`` — asimetría INTENCIONAL vs ``complete()``.

    Regresión: en ``complete()`` la response ya está leída y se le pasa el body a
    ``_raise_for_status(..., body_text=response.text)``, así un 400 de overflow se
    mapea a la subclase ``LlmContextOverflowError`` (P2.4). En ``stream()`` el
    ``_raise_for_status(response)`` se llama SIN ``body_text`` (el body es un stream
    aún no consumido), así que ``_is_context_overflow(None)`` da False y el 400 se
    mapea al ``LlmBadRequestError`` genérico. Este test fija esa diferencia para que
    un cambio futuro en el manejo del body de stream no la altere sin querer.
    """
    body = {"error": {"message": overflow_msg, "type": "BadRequestError"}}
    client = _client(lambda req: httpx.Response(400, json=body))
    with pytest.raises(LlmBadRequestError) as excinfo:
        async for _ in client.stream(model=_MODEL, messages=_messages()):
            pass
    # La subclase de overflow NO se gatilla por la rama de streaming.
    assert not isinstance(excinfo.value, LlmContextOverflowError)


@pytest.mark.asyncio
async def test_complete_timeout_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(handler)
    with pytest.raises(LlmTimeoutError):
        await client.complete(model=_MODEL, messages=_messages())


@pytest.mark.asyncio
async def test_complete_connect_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client(handler)
    with pytest.raises(LlmUnavailableError):
        await client.complete(model=_MODEL, messages=_messages())


# ---------- regla #4: el str(exc) de httpx no debe filtrar URL/host (S2) ----------

# httpx mete el host/URL real en el mensaje de sus excepciones (p.ej.
# "All connection attempts failed for http://vllm-test:8001"). Si eso viajara
# como ``detail`` de la excepcion LlmError, ``str(...)`` filtraria la base_url
# del modelo (regla #4). Estos tests fuerzan ese mensaje sensible y verifican
# que la etiqueta resultante es FIJA y que el httpx original solo viaja en
# ``__cause__`` (encadenamiento ``raise ... from exc``).
_LEAKY_HOST = "vllm-test:8001"


@pytest.mark.asyncio
async def test_complete_timeout_does_not_leak_host() -> None:
    leaky = f"timed out connecting to {_BASE_URL}"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(leaky, request=request)

    client = _client(handler)
    with pytest.raises(LlmTimeoutError) as excinfo:
        await client.complete(model=_MODEL, messages=_messages())

    rendered = str(excinfo.value)
    assert _LEAKY_HOST not in rendered
    assert _BASE_URL not in rendered
    assert rendered == "timeout de inferencia LLM: timeout HTTP"
    assert isinstance(excinfo.value.__cause__, httpx.TimeoutException)
    assert str(excinfo.value.__cause__) == leaky


@pytest.mark.asyncio
async def test_complete_connect_error_does_not_leak_host() -> None:
    leaky = f"All connection attempts failed for {_BASE_URL}"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(leaky, request=request)

    client = _client(handler)
    with pytest.raises(LlmUnavailableError) as excinfo:
        await client.complete(model=_MODEL, messages=_messages())

    rendered = str(excinfo.value)
    assert _LEAKY_HOST not in rendered
    assert _BASE_URL not in rendered
    assert rendered == "instancia LLM no disponible: connect error"
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)
    assert str(excinfo.value.__cause__) == leaky


@pytest.mark.asyncio
async def test_stream_timeout_does_not_leak_host() -> None:
    leaky = f"timed out connecting to {_BASE_URL}"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(leaky, request=request)

    client = _client(handler)
    with pytest.raises(LlmTimeoutError) as excinfo:
        async for _ in client.stream(model=_MODEL, messages=_messages()):
            pass

    rendered = str(excinfo.value)
    assert _LEAKY_HOST not in rendered
    assert _BASE_URL not in rendered
    assert rendered == "timeout de inferencia LLM: timeout HTTP"
    assert isinstance(excinfo.value.__cause__, httpx.TimeoutException)
    assert str(excinfo.value.__cause__) == leaky


@pytest.mark.asyncio
async def test_stream_connect_error_does_not_leak_host() -> None:
    leaky = f"All connection attempts failed for {_BASE_URL}"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(leaky, request=request)

    client = _client(handler)
    with pytest.raises(LlmUnavailableError) as excinfo:
        async for _ in client.stream(model=_MODEL, messages=_messages()):
            pass

    rendered = str(excinfo.value)
    assert _LEAKY_HOST not in rendered
    assert _BASE_URL not in rendered
    assert rendered == "instancia LLM no disponible: connect error"
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)
    assert str(excinfo.value.__cause__) == leaky


# ---------- streaming ----------


@pytest.mark.asyncio
async def test_stream_text_chunks() -> None:
    sse = (_FIXTURES / "stream_text.sse").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        return httpx.Response(
            200, content=sse.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    chunks = [chunk async for chunk in client.stream(model=_MODEL, messages=_messages())]
    texts = [c.delta_text for c in chunks if c.delta_text]
    assert "".join(texts) == "Hola mundo"
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_timeout_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(handler)
    with pytest.raises(LlmTimeoutError):
        async for _ in client.stream(model=_MODEL, messages=_messages()):
            pass


@pytest.mark.asyncio
async def test_stream_tool_call_deltas_accumulate() -> None:
    # E2E del streaming de tool calls: stream() emite tool_call_delta crudo y
    # el caller (router M8) lo junta con parser.accumulate(). test_stream_text
    # solo cubre texto; este cierra el shape {"choices": [choice]} con consumer.
    sse = (_FIXTURES / "stream_tool_calls.sse").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=sse.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    deltas = [
        chunk.tool_call_delta
        async for chunk in client.stream(model=_MODEL, messages=_messages())
        if chunk.tool_call_delta is not None
    ]
    calls = OpenAIToolCallParser().accumulate(deltas)
    assert len(calls) == 1
    assert calls[0].id == "call_stream_1"
    assert calls[0].name == "get_weather"
    assert calls[0].arguments == {"city": "Rosario"}


# ---------- health ----------


@pytest.mark.asyncio
async def test_health_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": _MODEL}]})

    client = _client(handler)
    health = await client.health()
    assert health.healthy is True
    assert health.model_name == _MODEL


@pytest.mark.asyncio
async def test_health_down_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client(handler)
    health = await client.health()
    assert health.healthy is False


@pytest.mark.asyncio
async def test_health_down_on_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(handler)
    health = await client.health()
    assert health.healthy is False
