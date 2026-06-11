"""Tests de la factory de clientes LLM / embedder / reranker (P2).

Verifican el gate Fakes (dev/test, default) vs. clientes REALES
(``ResilientClient`` / ``VllmClient`` en production) SIN abrir red: solo asserts
de tipo. ``httpx.AsyncClient`` no disca hasta el primer request, asi que
construir un ``VllmClient`` real es seguro sin un servidor vLLM levantado.

Tambien cubren el gate del embedder (``embedding_backend``) y el reranker.
"""

from __future__ import annotations

from app.core.config import Settings
from app.llm.clients.embedding import FakeEmbeddingClient, VllmEmbeddingClient
from app.llm.clients.factory import (
    build_embedder,
    build_llm_client,
    build_llm_clients,
    build_reranker,
)
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker, VllmReranker
from app.llm.clients.resilient import ResilientClient
from app.llm.config import (
    LlmRuntimeConfig,
    ModeConfig,
    ModelConfig,
    ServingConfig,
    Topology,
)

_QWEN = "qwen-3.5-9b"
_PRIMARY_URL = "http://primary:8001/v1"
_SECONDARY_URL = "http://secondary:8002/v1"

# JWT secret >= 32 chars: production rechaza un secret debil (ver Settings).
_PROD_JWT_SECRET = "x" * 48
_PROD_MASTER_KEY = "dGVzdC1tYXN0ZXIta2V5LTMyLWJ5dGVzLWxvbmctYWE="  # base64 placeholder


def _settings(
    *,
    environment: str = "development",
    embedding_backend: str = "fake",
    reranker_backend: str = "fake",
    llm_backend: str = "fake",
    topology: str = "split_process",
) -> Settings:
    """Settings aislado de cualquier .env. ``production`` exige config no-dev."""
    kwargs: dict[str, object] = {
        "_env_file": None,
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "REDIS_URL": "redis://localhost:6379/0",
        # ``environment`` no tiene alias: se setea por nombre de campo, no por env var.
        "environment": environment,
        "EMBEDDING_BACKEND": embedding_backend,
        "RERANKER_BACKEND": reranker_backend,
        "LLM_BACKEND": llm_backend,
        "LLM_TOPOLOGY": topology,
        "LLM_PRIMARY_BASE_URL": _PRIMARY_URL,
        "LLM_SECONDARY_BASE_URL": _SECONDARY_URL,
    }
    if environment == "production":
        # production fail-fast: secret fuerte, CORS no-localhost, master key.
        # ``cors_origins`` no tiene alias: se setea por nombre de campo.
        kwargs["JWT_SECRET"] = _PROD_JWT_SECRET
        kwargs["MEMORY_ENCRYPTION_MASTER_KEY"] = _PROD_MASTER_KEY
        kwargs["cors_origins"] = ["https://app.ynara.test"]
    else:
        kwargs["JWT_SECRET"] = "test-secret"
    return Settings(**kwargs)  # type: ignore[arg-type]


def _config(topology: Topology = "split_process") -> LlmRuntimeConfig:
    """``LlmRuntimeConfig`` minimo coherente con base_urls que matchean settings."""
    serving = ServingConfig(
        tool_parsers={_QWEN: "hermes"},
        quantization="awq_marlin",
        kv_cache_dtype="fp8",
        max_model_len={_QWEN: 32768},
        request_timeout_s=120,
    )
    models = {
        _QWEN: ModelConfig(
            key=_QWEN,
            role="agent",
            writes_memory=True,
            served_name="qwen",
            context_window=262144,
        )
    }
    modes = {
        "productividad": ModeConfig(
            name="productividad",
            model=_QWEN,
            memory_layers=["semantic"],
            tools_enabled=["memory"],
            tone="neutro",
        )
    }
    return LlmRuntimeConfig(
        primary_base_url=_PRIMARY_URL,
        secondary_base_url=_SECONDARY_URL,
        topology=topology,
        serving=serving,
        models=models,
        modes=modes,
    )


# ---------- build_llm_client ----------


def test_llm_client_is_fake_in_dev() -> None:
    """En development (default) la factory devuelve el ``FakeLlmClient``."""
    client = build_llm_client(_settings(environment="development"), _config())
    assert isinstance(client, FakeLlmClient)
    # Sirve el set de served_name de la config (incluye 'qwen').
    assert client.serves_model("qwen")


def test_llm_client_is_fake_in_staging() -> None:
    """staging tampoco tiene GPU: serving real solo en production."""
    client = build_llm_client(_settings(environment="staging"), _config())
    assert isinstance(client, FakeLlmClient)


def test_llm_client_is_resilient_in_production() -> None:
    """En production la factory devuelve el ``ResilientClient`` real (sin red)."""
    client = build_llm_client(_settings(environment="production"), _config())
    assert isinstance(client, ResilientClient)
    # El pool real sirve el served_name de la config (routing por modelo).
    assert client.serves_model("qwen")


def test_llm_client_production_single_process_one_client() -> None:
    """single_process: el pool real se arma con un solo VllmClient (solo primary)."""
    settings = _settings(environment="production", topology="single_process")
    client = build_llm_client(settings, _config("single_process"))
    assert isinstance(client, ResilientClient)
    assert client.serves_model("qwen")


def test_llm_client_is_real_when_backend_vllm_in_dev() -> None:
    """LLM_BACKEND=vllm prende el serving real en dev sin tocar environment."""
    client = build_llm_client(_settings(environment="development", llm_backend="vllm"), _config())
    assert isinstance(client, ResilientClient)
    assert client.serves_model("qwen")


# ---------- build_embedder ----------


def test_embedder_is_fake_by_default() -> None:
    embedder = build_embedder(_settings(embedding_backend="fake"))
    assert isinstance(embedder, FakeEmbeddingClient)


def test_embedder_is_vllm_when_backend_vllm() -> None:
    """``embedding_backend='vllm'`` construye el cliente real (sin abrir red)."""
    embedder = build_embedder(_settings(embedding_backend="vllm"))
    assert isinstance(embedder, VllmEmbeddingClient)


def test_embedder_vllm_takes_timeout_from_settings() -> None:
    """El timeout del embedder sale de Settings (review PR #198, MEDIUM #1)."""
    settings = _settings(embedding_backend="vllm").model_copy(update={"embedding_timeout_s": 12.5})
    embedder = build_embedder(settings)
    assert isinstance(embedder, VllmEmbeddingClient)
    assert embedder._default_timeout_s == 12.5


# ---------- build_reranker ----------


def test_reranker_is_fake_by_default() -> None:
    reranker = build_reranker(_settings())
    assert isinstance(reranker, FakeReranker)


def test_reranker_is_vllm_when_backend_vllm() -> None:
    """``reranker_backend='vllm'`` construye el VllmReranker real (sin abrir red)."""
    reranker = build_reranker(_settings(reranker_backend="vllm"))
    assert isinstance(reranker, VllmReranker)


def test_reranker_vllm_takes_timeout_from_settings() -> None:
    """El timeout del reranker sale de Settings (review PR #198, MEDIUM #1)."""
    settings = _settings(reranker_backend="vllm").model_copy(update={"reranker_timeout_s": 12.5})
    reranker = build_reranker(settings)
    assert isinstance(reranker, VllmReranker)
    assert reranker._default_timeout_s == 12.5


# ---------- build_llm_clients (trio) ----------


def test_build_llm_clients_returns_trio_of_fakes_in_dev() -> None:
    llm, embedder, reranker = build_llm_clients(_settings(), _config())
    assert isinstance(llm, FakeLlmClient)
    assert isinstance(embedder, FakeEmbeddingClient)
    assert isinstance(reranker, FakeReranker)


def test_build_llm_clients_returns_real_llm_in_production() -> None:
    settings = _settings(environment="production")
    llm, embedder, reranker = build_llm_clients(settings, _config())
    assert isinstance(llm, ResilientClient)
    # embedder/reranker reales aun no existen: siguen siendo Fakes detras del gate.
    assert isinstance(embedder, FakeEmbeddingClient)
    assert isinstance(reranker, FakeReranker)
