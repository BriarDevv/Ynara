"""Carga y validacion de la config de runtime del LLM (ADR-013).

Fusiona dos fuentes en un unico objeto inmutable:

- ``ynara.config.json`` — contrato de producto: ``models`` (con
  ``served_name``), ``modes`` y el bloque ``llm.serving`` (parsers,
  quantization, ``max_model_len``, timeouts).
- ``Settings`` (``.env``) — valores por entorno: la lista ``LLM_SERVING``
  con cada proceso de serving (vLLM o Ollama; su base_url y los served_names
  que sirve, ADR-013).

``load_llm_config()`` es fail-fast: levanta ``LlmConfigError`` con un
mensaje claro si la config es incoherente (modo que apunta a un modelo
inexistente, modelo sin ``served_name``, o ``max_model_len`` /
``tool_parser`` faltante para un modelo). Esta cacheado a nivel de modulo
para no releer el JSON en cada llamada.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import ServingEndpoint, Settings, get_settings

# ``config.py`` vive en apps/backend/app/llm/; la raiz del repo esta 4
# niveles arriba (llm -> app -> backend -> apps -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_PATH = _REPO_ROOT / "ynara.config.json"


class LlmConfigError(RuntimeError):
    """Config de LLM incoherente o ilegible. Fail-fast en el arranque."""


class ServingConfig(BaseModel):
    """Bloque ``llm.serving`` de ``ynara.config.json``.

    Perfil de serving para vLLM/24GB+ (ADR-014 D5); en Ollama estos campos se
    validan pero no se pasan al servidor (Ollama maneja quantization/kv-cache
    internamente). El schema los admite tal cual vienen del JSON.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tool_parsers: dict[str, str]
    quantization: str
    kv_cache_dtype: str
    max_model_len: dict[str, int]
    request_timeout_s: int = Field(gt=0)


class ModelConfig(BaseModel):
    """Un modelo de ``ynara.config.json[models][<key>]``.

    ``key`` es la clave del dict (p.ej. ``qwen-3.5-9b``); ``served_name``
    es el alias del modelo publicado por Ollama (o el ``--served-model-name``
    en vLLM/24GB+).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    key: str
    role: Literal["conversational", "agent"]
    writes_memory: bool
    served_name: str
    context_window: int = Field(gt=0)


class ModeConfig(BaseModel):
    """Un modo de ``ynara.config.json[modes][<key>]``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str
    model: str
    memory_layers: list[str]
    tools_enabled: list[str]
    tone: str


class LlmRuntimeConfig(BaseModel):
    """Config de runtime ya fusionada y validada.

    Inmutable: se construye una vez en el arranque via ``load_llm_config()``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    serving_endpoints: list[ServingEndpoint]
    serving: ServingConfig
    models: dict[str, ModelConfig]
    modes: dict[str, ModeConfig]

    def model_for_mode(self, mode: str) -> ModelConfig:
        """Devuelve la config del modelo que sirve un modo dado."""
        mode_cfg = self.modes.get(mode)
        if mode_cfg is None:
            raise LlmConfigError(f"modo desconocido: {mode!r}")
        return self.models[mode_cfg.model]

    def tool_parser_for(self, model_key: str) -> str:
        """``--tool-call-parser`` (flag del server vLLM) para un modelo."""
        return self.serving.tool_parsers[model_key]


def _read_config_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LlmConfigError(f"no se pudo leer {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmConfigError(f"{path} no es JSON valido: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmConfigError(f"{path} debe ser un objeto JSON en el top-level")
    return data


def _build_runtime_config(data: dict[str, object], settings: Settings) -> LlmRuntimeConfig:
    raw_models = data.get("models")
    raw_modes = data.get("modes")
    raw_llm = data.get("llm")
    if not isinstance(raw_models, dict):
        raise LlmConfigError("falta el bloque 'models' en ynara.config.json")
    if not isinstance(raw_modes, dict):
        raise LlmConfigError("falta el bloque 'modes' en ynara.config.json")
    if not isinstance(raw_llm, dict) or not isinstance(raw_llm.get("serving"), dict):
        raise LlmConfigError("falta el bloque 'llm.serving' en ynara.config.json")

    try:
        serving = ServingConfig.model_validate(raw_llm["serving"])
        models = {
            key: ModelConfig.model_validate({"key": key, **value})
            for key, value in raw_models.items()
        }
        modes = {
            name: ModeConfig.model_validate({"name": name, **value})
            for name, value in raw_modes.items()
        }
    except (TypeError, ValueError) as exc:
        # Pydantic ValidationError es subclase de ValueError; envolvemos
        # para que el caller solo tenga que atrapar LlmConfigError.
        raise LlmConfigError(f"ynara.config.json invalido: {exc}") from exc

    _validate_coherence(serving, settings.llm_serving, models, modes)

    return LlmRuntimeConfig(
        serving_endpoints=settings.llm_serving,
        serving=serving,
        models=models,
        modes=modes,
    )


def _validate_coherence(
    serving: ServingConfig,
    serving_endpoints: list[ServingEndpoint],
    models: dict[str, ModelConfig],
    modes: dict[str, ModeConfig],
) -> None:
    """Chequeos cross-field que Pydantic no puede hacer aislado."""
    for name, mode in modes.items():
        if mode.model not in models:
            raise LlmConfigError(f"modo {name!r} apunta a un modelo inexistente: {mode.model!r}")
        # Si el modo tiene 'memory' en tools_enabled, debe tener 'semantic' en
        # memory_layers: sin semantic_store no se puede construir memory_registry
        # y memory.search quedaria silenciosamente sin backend (decision #4 M8).
        if "memory" in mode.tools_enabled and "semantic" not in mode.memory_layers:
            raise LlmConfigError(
                f"modo {name!r} tiene 'memory' en tools_enabled pero le falta "
                f"'semantic' en memory_layers (sin semantic store, memory.search "
                f"no tiene backend)"
            )

    for key, model in models.items():
        if not model.served_name:
            raise LlmConfigError(f"modelo {key!r} no tiene served_name")
        if key not in serving.tool_parsers:
            raise LlmConfigError(
                f"falta tool_parser para el modelo {key!r} en llm.serving.tool_parsers"
            )
        if key not in serving.max_model_len:
            raise LlmConfigError(
                f"falta max_model_len para el modelo {key!r} en llm.serving.max_model_len"
            )
        if serving.max_model_len[key] > model.context_window:
            raise LlmConfigError(
                f"max_model_len para {key!r} ({serving.max_model_len[key]}) supera el "
                f"context_window del modelo ({model.context_window})"
            )

    # ADR-013: validar la lista LLM_SERVING (fail-fast: un .env mal armado no
    # debe bootear con ruteo roto o un httpx.AsyncClient huerfano).
    if not serving_endpoints:
        raise LlmConfigError(
            "LLM_SERVING está vacío: declarar al menos un proceso de serving (vLLM o Ollama)"
        )
    served_names = {model.served_name for model in models.values()}
    seen_base_urls: set[str] = set()
    for entry in serving_endpoints:
        # base_url duplicada: el factory keyea por base_url -> el 2do client
        # pisaria al 1ro (su httpx queda huerfano, nunca se cierra) y el pool
        # tendria dos slots al MISMO client. N instancias = N base_urls distintas.
        if entry.base_url in seen_base_urls:
            raise LlmConfigError(f"LLM_SERVING: base_url duplicada: {entry.base_url!r}")
        seen_base_urls.add(entry.base_url)
        # entrada sin models: el client nunca seria elegido (serves_model->False)
        # y el modelo daria ModelNotServedError en runtime sin aviso al boot.
        if not entry.models:
            raise LlmConfigError(f"LLM_SERVING: la entrada {entry.base_url!r} no declara 'models'")
        for name in entry.models:
            if name not in served_names:
                raise LlmConfigError(f"LLM_SERVING referencia served_name desconocido: {name!r}")


def load_llm_config(
    *, config_path: Path | None = None, settings: Settings | None = None
) -> LlmRuntimeConfig:
    """Carga y valida la config de runtime del LLM.

    Inyectable para tests (``config_path`` / ``settings``); sin argumentos
    usa ``ynara.config.json`` de la raiz del repo + el singleton de
    settings, y cachea el resultado.
    """
    if config_path is None and settings is None:
        return _load_cached()
    resolved_settings = settings if settings is not None else get_settings()
    resolved_path = config_path if config_path is not None else _CONFIG_PATH
    return _build_runtime_config(_read_config_file(resolved_path), resolved_settings)


@lru_cache(maxsize=1)
def _load_cached() -> LlmRuntimeConfig:
    return _build_runtime_config(_read_config_file(_CONFIG_PATH), get_settings())
