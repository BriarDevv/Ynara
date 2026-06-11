"""Contract tests del ``VllmEmbeddingClient`` con ``httpx.MockTransport``.

Sin red ni GPU: inyectamos un ``httpx.AsyncClient`` con un handler que devuelve
respuestas del shape OpenAI de ``/v1/embeddings``. Cubrimos: payload conforme,
parseo a ``list[list[float]]`` respetando el orden por ``index``, short-circuit
de batch vacio, mapeo de errores HTTP y que la etiqueta NO filtra host (regla #4).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.llm.clients.embedding import EmbeddingClient, VllmEmbeddingClient
from app.llm.errors import (
    LlmBadRequestError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
)

_BASE_URL = "http://embed-test:8003/v1"

_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> VllmEmbeddingClient:
    transport = httpx.MockTransport(handler)
    return VllmEmbeddingClient(
        base_url=_BASE_URL,
        http_client=httpx.AsyncClient(transport=transport),
        model="bge-m3",
    )


def _ok(vectors: list[list[float]]) -> httpx.Response:
    data = [{"index": i, "embedding": v} for i, v in enumerate(vectors)]
    return httpx.Response(200, json={"data": data, "model": "bge-m3"})


# ---------- conformance ----------


def test_conforms_to_protocol() -> None:
    assert isinstance(_client(lambda req: _ok([[0.0]])), EmbeddingClient)


# ---------- embed OK ----------


async def test_embed_posts_openai_payload_to_embeddings_endpoint() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return _ok([[0.1, 0.2], [0.3, 0.4]])

    result = await _client(handler).embed(["hola", "chau"])

    assert captured["path"] == "/v1/embeddings"
    assert captured["method"] == "POST"
    assert captured["body"] == {"model": "bge-m3", "input": ["hola", "chau"]}
    assert result == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_orders_by_index() -> None:
    # La respuesta llega desordenada; el cliente reordena por ``index``.
    def handler(request: httpx.Request) -> httpx.Response:
        data = [
            {"index": 1, "embedding": [9.0]},
            {"index": 0, "embedding": [1.0]},
        ]
        return httpx.Response(200, json={"data": data})

    result = await _client(handler).embed(["a", "b"])
    assert result == [[1.0], [9.0]]


async def test_embed_uses_configured_default_timeout() -> None:
    # El timeout por request sale de default_timeout_s (la factory lo toma de
    # Settings.embedding_timeout_s); sin esto quedaria hardcodeado en 30s.
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions["timeout"]
        return _ok([[0.1]])

    client = VllmEmbeddingClient(
        base_url=_BASE_URL,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        model="bge-m3",
        default_timeout_s=12.5,
    )
    await client.embed(["a"])
    assert captured["timeout"]["read"] == 12.5


async def test_embed_empty_batch_short_circuits_without_request() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _ok([])

    result = await _client(handler).embed([])
    assert result == []
    assert called is False


# ---------- respuestas malformadas ----------


async def test_embed_wrong_count_raises_llm_error() -> None:
    # data con menos vectores que textos pedidos: respuesta incoherente.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    with pytest.raises(LlmError):
        await _client(handler).embed(["a", "b"])


async def test_embed_missing_data_raises_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "bge-m3"})

    with pytest.raises(LlmError):
        await _client(handler).embed(["a"])


# ---------- mapeo de errores HTTP ----------


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
async def test_embed_maps_http_errors(status: int, expected: type[LlmError]) -> None:
    with pytest.raises(expected):
        await _client(lambda req: httpx.Response(status, json={"error": "x"})).embed(["a"])


async def test_embed_timeout_maps_to_llm_timeout_without_leaking_host() -> None:
    leaky = f"timed out connecting to {_BASE_URL}"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(leaky, request=request)

    with pytest.raises(LlmTimeoutError) as excinfo:
        await _client(handler).embed(["a"])
    # Regla #4: la etiqueta es fija; el host viaja solo en __cause__.
    assert _BASE_URL not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, httpx.TimeoutException)


async def test_embed_connect_error_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LlmUnavailableError):
        await _client(handler).embed(["a"])


# ---------- health ----------


async def test_health_ok_when_models_endpoint_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

    health = await _client(handler).health()
    assert health.healthy is True
    assert health.model_name == "bge-m3"


async def test_health_unhealthy_on_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    assert (await _client(handler).health()).healthy is False


async def test_health_unhealthy_on_non_200() -> None:
    # Un server que responde 503 (o cualquier non-200) en /models es unhealthy.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    assert (await _client(handler).health()).healthy is False
