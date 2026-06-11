"""Contract tests del ``VllmReranker`` con ``httpx.MockTransport``.

Sin red ni GPU: inyectamos un ``httpx.AsyncClient`` con un handler que devuelve
el shape rerank estilo Cohere/Jina de vLLM (``/v1/rerank``). Cubrimos: payload
conforme, reorden por ``relevance_score`` desc, ``top_n`` (omitido si None /
recorte defensivo), short-circuit de documents vacio y mapeo de errores HTTP.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.llm.clients.reranker import Reranker, VllmReranker
from app.llm.errors import (
    LlmBadRequestError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
)

_BASE_URL = "http://rerank-test:8004/v1"

_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> VllmReranker:
    transport = httpx.MockTransport(handler)
    return VllmReranker(
        base_url=_BASE_URL,
        http_client=httpx.AsyncClient(transport=transport),
        model="bge-reranker-v2-m3",
    )


def _results(pairs: list[tuple[int, float]]) -> httpx.Response:
    results = [{"index": i, "relevance_score": s} for i, s in pairs]
    return httpx.Response(200, json={"results": results})


# ---------- conformance ----------


def test_conforms_to_protocol() -> None:
    assert isinstance(_client(lambda req: _results([(0, 1.0)])), Reranker)


# ---------- rerank OK ----------


async def test_rerank_posts_cohere_style_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return _results([(0, 0.9), (1, 0.1)])

    results = await _client(handler).rerank(query="q", documents=["a", "b"], top_n=2)

    assert captured["path"] == "/v1/rerank"
    assert captured["body"] == {
        "model": "bge-reranker-v2-m3",
        "query": "q",
        "documents": ["a", "b"],
        "top_n": 2,
    }
    assert [(r.index, r.score) for r in results] == [(0, 0.9), (1, 0.1)]


async def test_rerank_reorders_by_score_desc() -> None:
    # El server manda desordenado; el cliente reordena por score desc.
    def handler(request: httpx.Request) -> httpx.Response:
        return _results([(0, 0.2), (1, 0.8)])

    results = await _client(handler).rerank(query="q", documents=["a", "b"])
    assert [r.index for r in results] == [1, 0]
    assert results[0].score == 0.8


async def test_rerank_omits_top_n_when_none() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _results([(0, 1.0)])

    await _client(handler).rerank(query="q", documents=["a"])
    assert "top_n" not in captured["body"]


async def test_rerank_truncates_to_top_n_defensively() -> None:
    # Si el server ignora top_n y devuelve de mas, el cliente recorta.
    def handler(request: httpx.Request) -> httpx.Response:
        return _results([(0, 0.9), (1, 0.5), (2, 0.1)])

    results = await _client(handler).rerank(query="q", documents=["a", "b", "c"], top_n=2)
    assert len(results) == 2
    assert [r.index for r in results] == [0, 1]


async def test_rerank_uses_configured_default_timeout() -> None:
    # El timeout por request sale de default_timeout_s (la factory lo toma de
    # Settings.reranker_timeout_s); sin esto quedaria hardcodeado en 30s.
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions["timeout"]
        return _results([(0, 1.0)])

    client = VllmReranker(
        base_url=_BASE_URL,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        model="bge-reranker-v2-m3",
        default_timeout_s=12.5,
    )
    await client.rerank(query="q", documents=["a"])
    assert captured["timeout"]["read"] == 12.5


async def test_rerank_empty_documents_short_circuits() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _results([])

    results = await _client(handler).rerank(query="q", documents=[])
    assert results == []
    assert called is False


# ---------- respuestas malformadas ----------


async def test_rerank_missing_results_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    with pytest.raises(LlmError):
        await _client(handler).rerank(query="q", documents=["a"])


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
async def test_rerank_maps_http_errors(status: int, expected: type[LlmError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "x"})

    with pytest.raises(expected):
        await _client(handler).rerank(query="q", documents=["a"])


async def test_rerank_timeout_maps_to_llm_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow", request=request)

    with pytest.raises(LlmTimeoutError):
        await _client(handler).rerank(query="q", documents=["a"])


# ---------- health ----------


async def test_health_ok_when_models_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

    health = await _client(handler).health()
    assert health.healthy is True
    assert health.model_name == "bge-reranker-v2-m3"
