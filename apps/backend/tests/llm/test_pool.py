"""Tests del ``ClientPool`` + ``build_pool`` (M3).

Usan ``FakeLlmClient`` como doble: no hay red. Verifican el filtrado por
``serves_model``, la estrategia de ruteo, el error cuando nadie sirve el
modelo, y el armado de la topologia.
"""

from __future__ import annotations

import pytest

from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.pool import ClientPool, FirstHealthy, RoutingStrategy, build_pool
from app.llm.config import (
    LlmRuntimeConfig,
    ModeConfig,
    ModelConfig,
    ServingConfig,
    Topology,
)
from app.llm.errors import ModelNotServedError

_QWEN = "qwen-3.5-9b"
_GEMMA = "gemma-4-26b-a4b"
_PRIMARY_URL = "http://primary:8001/v1"
_SECONDARY_URL = "http://secondary:8002/v1"


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


def _config(topology: Topology) -> LlmRuntimeConfig:
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


def test_build_pool_split_process_has_two_clients() -> None:
    primary = _fake(_QWEN)
    secondary = _fake(_QWEN)
    clients_by_url = {_PRIMARY_URL: primary, _SECONDARY_URL: secondary}
    pool = build_pool(_config("split_process"), clients_by_url)
    assert pool.clients == [primary, secondary]


def test_build_pool_single_process_has_one_client() -> None:
    primary = _fake(_QWEN)
    secondary = _fake(_QWEN)
    clients_by_url = {_PRIMARY_URL: primary, _SECONDARY_URL: secondary}
    pool = build_pool(_config("single_process"), clients_by_url)
    assert pool.clients == [primary]


def test_build_pool_swap_lru_has_one_client() -> None:
    primary = _fake(_QWEN)
    clients_by_url = {_PRIMARY_URL: primary}
    pool = build_pool(_config("swap_lru"), clients_by_url)
    assert pool.clients == [primary]


def test_build_pool_missing_secondary_raises() -> None:
    primary = _fake(_QWEN)
    clients_by_url = {_PRIMARY_URL: primary}  # falta el secundario
    with pytest.raises(KeyError):
        build_pool(_config("split_process"), clients_by_url)
