"""Tests del ``ClientPool`` + ``build_pool`` (M3).

Usan ``FakeLlmClient`` como doble: no hay red. Verifican el filtrado por
``serves_model``, la estrategia de ruteo, el error cuando nadie sirve el
modelo, y el armado de la topologia.
"""

from __future__ import annotations

import pytest

from app.core.config import ServingEndpoint
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.pool import ClientPool, FirstHealthy, RoutingStrategy, build_pool
from app.llm.config import (
    LlmRuntimeConfig,
    ModeConfig,
    ModelConfig,
    ServingConfig,
)
from app.llm.errors import ModelNotServedError

_QWEN = "qwen-3.5-9b"
_GEMMA = "gemma-4-12b"
_GEMMA_URL = "http://gemma:8001/v1"
_QWEN_URL = "http://qwen:8002/v1"


def _fake(model: str) -> FakeLlmClient:
    return FakeLlmClient(served_models=frozenset({model}))


def _pool(clients: list[FakeLlmClient], strategy: RoutingStrategy | None = None) -> ClientPool:
    return ClientPool(list(clients), strategy or FirstHealthy())


# ---------- candidates ----------


def test_candidates_filters_by_serves_model() -> None:
    qwen = _fake(_QWEN)
    gemma = _fake(_GEMMA)
    pool = _pool([qwen, gemma])
    assert pool.candidates(_QWEN) == [qwen]
    assert pool.candidates(_GEMMA) == [gemma]
    assert pool.candidates("no-servido") == []


def test_candidates_preserves_pool_order() -> None:
    primary = _fake(_QWEN)
    secondary = _fake(_QWEN)
    pool = _pool([primary, secondary])
    assert pool.candidates(_QWEN) == [primary, secondary]


# ---------- pick ----------


def test_pick_returns_first_healthy() -> None:
    primary = _fake(_QWEN)
    secondary = _fake(_QWEN)
    pool = _pool([primary, secondary])
    assert pool.pick(_QWEN) is primary


def test_pick_uses_strategy() -> None:
    primary = _fake(_QWEN)
    secondary = _fake(_QWEN)

    class _PickLast:
        def pick(self, candidates: list[object]) -> object:
            return candidates[-1]

    pool = _pool([primary, secondary], strategy=_PickLast())  # type: ignore[arg-type]
    assert pool.pick(_QWEN) is secondary


def test_pick_without_candidates_raises() -> None:
    pool = _pool([_fake(_QWEN)])
    with pytest.raises(ModelNotServedError):
        pool.pick("no-servido")


def test_first_healthy_satisfies_protocol() -> None:
    assert isinstance(FirstHealthy(), RoutingStrategy)


# ---------- build_pool ----------


def _config(serving_endpoints: list[ServingEndpoint]) -> LlmRuntimeConfig:
    """``LlmRuntimeConfig`` con la lista ``serving_endpoints`` dada (ADR-013).

    ``models`` declara gemma + qwen (served_name ``gemma4`` / ``qwen``) para que
    los tests puedan rutear cualquiera de los dos.
    """
    serving = ServingConfig(
        tool_parsers={_QWEN: "hermes", _GEMMA: "gemma4"},
        quantization="awq_marlin",
        kv_cache_dtype="fp8",
        max_model_len={_QWEN: 32768, _GEMMA: 8192},
        request_timeout_s=120,
    )
    models = {
        _QWEN: ModelConfig(
            key=_QWEN,
            role="agent",
            writes_memory=True,
            served_name="qwen",
            context_window=262144,
        ),
        _GEMMA: ModelConfig(
            key=_GEMMA,
            role="conversational",
            writes_memory=False,
            served_name="gemma4",
            context_window=128000,
        ),
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
        serving_endpoints=serving_endpoints,
        serving=serving,
        models=models,
        modes=modes,
    )


def test_build_pool_orders_clients_by_serving_list() -> None:
    """``build_pool`` arma el pool en el orden de ``serving_endpoints``."""
    gemma = _fake("gemma4")
    qwen = _fake("qwen")
    clients_by_url = {_GEMMA_URL: gemma, _QWEN_URL: qwen}
    cfg = _config(
        [
            ServingEndpoint(base_url=_GEMMA_URL, models=["gemma4"]),
            ServingEndpoint(base_url=_QWEN_URL, models=["qwen"]),
        ]
    )
    pool = build_pool(cfg, clients_by_url)
    assert pool.clients == [gemma, qwen]


def test_build_pool_single_entry_has_one_client() -> None:
    """Una sola entrada (caso Ollama dev) = un solo client en el pool."""
    only = _fake("qwen")
    clients_by_url = {_QWEN_URL: only}
    cfg = _config([ServingEndpoint(base_url=_QWEN_URL, models=["qwen"])])
    pool = build_pool(cfg, clients_by_url)
    assert pool.clients == [only]


def test_build_pool_missing_client_for_base_url_raises() -> None:
    """Falta un client para una base_url declarada -> KeyError (fail-fast)."""
    gemma = _fake("gemma4")
    clients_by_url = {_GEMMA_URL: gemma}  # falta el de qwen
    cfg = _config(
        [
            ServingEndpoint(base_url=_GEMMA_URL, models=["gemma4"]),
            ServingEndpoint(base_url=_QWEN_URL, models=["qwen"]),
        ]
    )
    with pytest.raises(KeyError):
        build_pool(cfg, clients_by_url)


def test_pool_routes_each_model_to_its_own_process() -> None:
    """Regression #206: cada client anuncia solo SUS served_names.

    Con 2 entradas (gemma en url1, qwen en url2), ``pick('qwen')`` devuelve el
    client de url2 (no el de gemma, que es el primero del pool) y ``pick('gemma4')``
    el de url1. Antes de ADR-013 ambos clients anunciaban el set completo y el
    pool ruteaba qwen al proceso de gemma (FirstHealthy) -> 404.
    """
    gemma = _fake("gemma4")
    qwen = _fake("qwen")
    clients_by_url = {_GEMMA_URL: gemma, _QWEN_URL: qwen}
    cfg = _config(
        [
            ServingEndpoint(base_url=_GEMMA_URL, models=["gemma4"]),
            ServingEndpoint(base_url=_QWEN_URL, models=["qwen"]),
        ]
    )
    pool = build_pool(cfg, clients_by_url)
    assert pool.pick("qwen") is qwen
    assert pool.pick("gemma4") is gemma
