"""Tests de carga y fail-fast de ``load_llm_config`` (M0).

Cubren la carga OK contra el ``ynara.config.json`` real del repo y cada
caso incoherente que debe disparar ``LlmConfigError``: modo que apunta a
un modelo inexistente, modelo sin ``served_name``, y tool_parser /
max_model_len faltante.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.llm.config import LlmConfigError, LlmRuntimeConfig, load_llm_config


def _settings() -> Settings:
    """Settings aislado de cualquier .env, con los campos minimos."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret",
    )


def _base_config() -> dict[str, Any]:
    """Config minima coherente, base para mutar en los tests de fail-fast."""
    return {
        "modes": {
            "productividad": {
                "model": "qwen-3.5-9b",
                "memory_layers": ["semantic", "episodic"],
                "tools_enabled": ["calendar", "memory"],
                "tone": "neutro-eficaz",
            },
        },
        "models": {
            "qwen-3.5-9b": {
                "role": "agent",
                "writes_memory": True,
                "served_name": "qwen",
                "context_window": 262144,
            },
        },
        "llm": {
            "serving": {
                "tool_parsers": {"qwen-3.5-9b": "hermes"},
                "quantization": "awq_marlin",
                "kv_cache_dtype": "fp8",
                "max_model_len": {"qwen-3.5-9b": 32768},
                "request_timeout_s": 120,
            }
        },
    }


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "ynara.config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------- Carga OK ----------


def test_load_real_repo_config() -> None:
    """El ``ynara.config.json`` real del repo carga sin errores."""
    cfg = load_llm_config(settings=_settings())
    assert isinstance(cfg, LlmRuntimeConfig)
    assert set(cfg.models) == {"gemma-4-26b-a4b", "qwen-3.5-9b"}
    assert cfg.topology == "split_process"
    assert cfg.primary_base_url == "http://localhost:8001/v1"
    # served_name y parser se resuelven por modo / modelo.
    assert cfg.model_for_mode("memoria").served_name == "qwen"
    assert cfg.tool_parser_for("gemma-4-26b-a4b") == "gemma4"
    assert cfg.serving.max_model_len["qwen-3.5-9b"] == 32768


def test_load_minimal_config(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_config())
    cfg = load_llm_config(config_path=path, settings=_settings())
    assert cfg.modes["productividad"].model == "qwen-3.5-9b"
    assert cfg.models["qwen-3.5-9b"].served_name == "qwen"
    assert cfg.serving.request_timeout_s == 120


def test_settings_override_base_urls_and_topology(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_config())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        JWT_SECRET="x",
        LLM_PRIMARY_BASE_URL="http://primary:9000/v1",
        LLM_SECONDARY_BASE_URL="http://secondary:9001/v1",
        LLM_TOPOLOGY="swap_lru",
    )
    cfg = load_llm_config(config_path=path, settings=settings)
    assert cfg.primary_base_url == "http://primary:9000/v1"
    assert cfg.secondary_base_url == "http://secondary:9001/v1"
    assert cfg.topology == "swap_lru"


# ---------- Fail-fast ----------


def test_mode_points_to_missing_model(tmp_path: Path) -> None:
    data = _base_config()
    data["modes"]["productividad"]["model"] = "no-existe"
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="inexistente"):
        load_llm_config(config_path=path, settings=_settings())


def test_model_without_served_name(tmp_path: Path) -> None:
    data = _base_config()
    data["models"]["qwen-3.5-9b"]["served_name"] = ""
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="served_name"):
        load_llm_config(config_path=path, settings=_settings())


def test_missing_tool_parser(tmp_path: Path) -> None:
    data = _base_config()
    data["llm"]["serving"]["tool_parsers"] = {}
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="tool_parser"):
        load_llm_config(config_path=path, settings=_settings())


def test_missing_max_model_len(tmp_path: Path) -> None:
    data = _base_config()
    data["llm"]["serving"]["max_model_len"] = {}
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="max_model_len"):
        load_llm_config(config_path=path, settings=_settings())


def test_max_model_len_exceeds_context_window(tmp_path: Path) -> None:
    data = _base_config()
    # context_window del modelo es 262144; pedir mas debe disparar fail-fast.
    data["llm"]["serving"]["max_model_len"]["qwen-3.5-9b"] = 262145
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="context_window"):
        load_llm_config(config_path=path, settings=_settings())


def test_missing_serving_block(tmp_path: Path) -> None:
    data = _base_config()
    del data["llm"]
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match=r"llm\.serving"):
        load_llm_config(config_path=path, settings=_settings())


def test_unknown_field_in_model_rejected(tmp_path: Path) -> None:
    """extra='forbid' rechaza campos no declarados (p.ej. el viejo endpoint)."""
    data = _base_config()
    data["models"]["qwen-3.5-9b"]["endpoint"] = "http://localhost:8001/v1"
    path = _write(tmp_path, data)
    with pytest.raises(LlmConfigError, match="invalido"):
        load_llm_config(config_path=path, settings=_settings())


def test_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "ynara.config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LlmConfigError, match="JSON"):
        load_llm_config(config_path=path, settings=_settings())


def test_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "no-existe.json"
    with pytest.raises(LlmConfigError, match="no se pudo leer"):
        load_llm_config(config_path=path, settings=_settings())


def test_mode_unknown_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_config())
    cfg = load_llm_config(config_path=path, settings=_settings())
    with pytest.raises(LlmConfigError, match="modo desconocido"):
        cfg.model_for_mode("inexistente")
