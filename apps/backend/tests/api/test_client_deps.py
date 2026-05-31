"""Tests unitarios de las deps get_llm_client / get_embedder / get_reranker.

Verifican que las tres deps lean de ``app.state`` y devuelvan exactamente
los singletons puestos ahí, sin tocar vLLM ni ningún servicio externo.

Estrategia:
- Tests con el lifespan real de ``app.main``: ejercita la construcción de
  FakeLlmClient/FakeEmbeddingClient/FakeReranker en startup sin servicios
  externos.
- Tests con ``app.state`` seteado a mano: prueban que las deps son thin
  wrappers sobre ``request.app.state.*`` sin lógica propia.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.deps import get_embedder, get_llm_client, get_reranker
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.config import load_llm_config

# ---------------------------------------------------------------------------
# Tests con el lifespan real
# ---------------------------------------------------------------------------


def test_lifespan_sets_fake_llm_client() -> None:
    """El lifespan pone un FakeLlmClient en app.state.llm_client."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True):
        assert isinstance(app.state.llm_client, FakeLlmClient)


def test_lifespan_sets_fake_embedding_client() -> None:
    """El lifespan pone un FakeEmbeddingClient en app.state.embedder."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True):
        assert isinstance(app.state.embedder, FakeEmbeddingClient)


def test_lifespan_sets_fake_reranker() -> None:
    """El lifespan pone un FakeReranker en app.state.reranker."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True):
        assert isinstance(app.state.reranker, FakeReranker)


def test_lifespan_llm_client_served_models_match_config() -> None:
    """FakeLlmClient recibe los served_name del config (no las keys del dict)."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True):
        cfg = load_llm_config()
        expected = frozenset(m.served_name for m in cfg.models.values())
        client: FakeLlmClient = app.state.llm_client
        # Probamos serves_model para no acoplar al atributo privado.
        for served_name in expected:
            assert client.serves_model(served_name), f"FakeLlmClient deberia servir '{served_name}'"


# ---------------------------------------------------------------------------
# Tests de deps como thin wrappers (app.state seteado a mano)
# ---------------------------------------------------------------------------
# Montamos una mini-app separada para no depender del lifespan aquí.


_mini = FastAPI()
_sentinel_llm = FakeLlmClient(served_models=frozenset({"qwen", "gemma4"}))
_sentinel_emb = FakeEmbeddingClient()
_sentinel_rer = FakeReranker()
_mini.state.llm_client = _sentinel_llm
_mini.state.embedder = _sentinel_emb
_mini.state.reranker = _sentinel_rer


@_mini.get("/_test/llm")
async def _route_llm(req: Request) -> dict:
    client = get_llm_client(req)
    return {"type": type(client).__name__, "is_sentinel": client is _sentinel_llm}


@_mini.get("/_test/embedder")
async def _route_emb(req: Request) -> dict:
    emb = get_embedder(req)
    return {"type": type(emb).__name__, "is_sentinel": emb is _sentinel_emb}


@_mini.get("/_test/reranker")
async def _route_rer(req: Request) -> dict:
    rer = get_reranker(req)
    return {"type": type(rer).__name__, "is_sentinel": rer is _sentinel_rer}


@pytest.fixture(scope="module")
def mini_client() -> TestClient:
    return TestClient(_mini)


def test_get_llm_client_returns_correct_type(mini_client: TestClient) -> None:
    """get_llm_client devuelve un FakeLlmClient desde app.state."""
    resp = mini_client.get("/_test/llm")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FakeLlmClient"


def test_get_llm_client_identity(mini_client: TestClient) -> None:
    """get_llm_client devuelve el *mismo* objeto (identidad), no una copia."""
    resp = mini_client.get("/_test/llm")
    assert resp.status_code == 200
    assert resp.json()["is_sentinel"] is True


def test_get_embedder_returns_correct_type(mini_client: TestClient) -> None:
    """get_embedder devuelve un FakeEmbeddingClient desde app.state."""
    resp = mini_client.get("/_test/embedder")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FakeEmbeddingClient"


def test_get_embedder_identity(mini_client: TestClient) -> None:
    """get_embedder devuelve el *mismo* objeto (identidad), no una copia."""
    resp = mini_client.get("/_test/embedder")
    assert resp.status_code == 200
    assert resp.json()["is_sentinel"] is True


def test_get_reranker_returns_correct_type(mini_client: TestClient) -> None:
    """get_reranker devuelve un FakeReranker desde app.state."""
    resp = mini_client.get("/_test/reranker")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FakeReranker"


def test_get_reranker_identity(mini_client: TestClient) -> None:
    """get_reranker devuelve el *mismo* objeto (identidad), no una copia."""
    resp = mini_client.get("/_test/reranker")
    assert resp.status_code == 200
    assert resp.json()["is_sentinel"] is True
