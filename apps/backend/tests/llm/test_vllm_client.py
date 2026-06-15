"""Contract tests del ``VllmClient`` con ``httpx.MockTransport`` (M2).

``MockTransport`` es nativo de httpx (no necesita ``respx``): inyectamos
un ``httpx.AsyncClient`` con un handler que devuelve respuestas grabadas
del shape OpenAI de vLLM. Cubrimos: complete con texto, complete con
tool_calls, mapeo de cada error HTTP, timeout / connect, streaming y
health.
"""

from __future__ import annotations

import json
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
from app.llm.schemas import ChatMessage, ToolSpec

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
async def test_complete_propagates_tool_parsing_error() -> None:
    # arguments malformado en la respuesta -> ToolParsingError sale por complete().
    body = _load("completion_bad_arguments.json")
    client = _client(lambda req: httpx.Response(200, json=body))
    with pytest.raises(ToolParsingError):
        await client.complete(model=_MODEL, messages=_messages())


# ---------- thinking por rol: reasoning_effort + chat_template_kwargs (#205) ----------
# reasoning_effort es el param que honra Ollama (motor 16GB, ADR-014); chat_template_kwargs
# cubre vLLM. Se emiten ambos; verificado contra Ollama real.


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
