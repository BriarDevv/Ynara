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
    """Settings aislado de cualquier .env, con los campos minimos.

    ``LLM_SERVING`` se setea explicito (1 entrada, served_name ``qwen``) para
    ser coherente con ``_base_config`` (que solo declara el modelo qwen). El
    default real referencia tambien ``gemma4``, ausente en la config minima.
    """
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret",
        LLM_SERVING=[{"base_url": "http://localhost:8002/v1", "models": ["qwen"]}],
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
    assert set(cfg.models) == {"gemma-4-12b", "qwen-3.5-9b"}
    # LLM_SERVING (ADR-013): la lista describe la topologia y cada entrada
    # referencia served_names validos (default = gemma4 + qwen, co-residente).
    assert cfg.serving_endpoints
    served_names = {model.served_name for model in cfg.models.values()}
    for entry in cfg.serving_endpoints:
        for name in entry.models:
            assert name in served_names
    # served_name y parser se resuelven por modo / modelo.
    assert cfg.model_for_mode("memoria").served_name == "qwen"
    assert cfg.tool_parser_for("gemma-4-12b") == "gemma4"
    assert cfg.serving.max_model_len["gemma-4-12b"] == 8192
    assert cfg.serving.max_model_len["qwen-3.5-9b"] == 32768


def test_load_minimal_config(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_config())
    cfg = load_llm_config(config_path=path, settings=_settings())
    assert cfg.modes["productividad"].model == "qwen-3.5-9b"
    assert cfg.models["qwen-3.5-9b"].served_name == "qwen"
    assert cfg.serving.request_timeout_s == 120


def test_settings_override_serving(tmp_path: Path) -> None:
    """``LLM_SERVING`` de Settings se refleja en ``cfg.serving_endpoints``."""
    path = _write(tmp_path, _base_config())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        JWT_SECRET="x",
        LLM_SERVING=[{"base_url": "http://primary:9000/v1", "models": ["qwen"]}],
    )
    cfg = load_llm_config(config_path=path, settings=settings)
    assert [ep.base_url for ep in cfg.serving_endpoints] == ["http://primary:9000/v1"]
    assert cfg.serving_endpoints[0].models == ["qwen"]


def test_serving_unknown_served_name_raises(tmp_path: Path) -> None:
    """``LLM_SERVING`` con un served_name inexistente dispara fail-fast (ADR-013)."""
    path = _write(tmp_path, _base_config())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        JWT_SECRET="x",
        LLM_SERVING=[{"base_url": "http://primary:9000/v1", "models": ["no-existe"]}],
    )
    with pytest.raises(LlmConfigError, match="served_name desconocido"):
        load_llm_config(config_path=path, settings=settings)


def test_serving_duplicate_base_url_raises(tmp_path: Path) -> None:
    """``LLM_SERVING`` con base_url repetida dispara fail-fast (ADR-013).

    El factory keyea por base_url: dos entradas con la misma URL pisarian un
    client (httpx huerfano) y el pool quedaria con dos slots al mismo client.
    """
    path = _write(tmp_path, _base_config())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        JWT_SECRET="x",
        LLM_SERVING=[
            {"base_url": "http://a:9000/v1", "models": ["qwen"]},
            {"base_url": "http://a:9000/v1", "models": ["qwen"]},
        ],
    )
    with pytest.raises(LlmConfigError, match="base_url duplicada"):
        load_llm_config(config_path=path, settings=settings)


def test_serving_empty_models_raises(tmp_path: Path) -> None:
    """``LLM_SERVING`` con una entrada sin models dispara fail-fast (ADR-013)."""
    path = _write(tmp_path, _base_config())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        JWT_SECRET="x",
        LLM_SERVING=[{"base_url": "http://a:9000/v1", "models": []}],
    )
    with pytest.raises(LlmConfigError, match="no declara 'models'"):
        load_llm_config(config_path=path, settings=settings)


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
