"""Carga y validacion de los thresholds de memoria (ADR-007 D1).

Parsea el sub-bloque de decay de ``ynara.config.json[memory]`` y lo expone
como un objeto inmutable. Espeja 1:1 la mecanica de ``app/llm/config.py``
(Pydantic frozen + strict + ``extra='forbid'`` + fail-fast envuelto en un
error tipado + cache ``lru_cache`` por modulo + inyectable para tests).

A diferencia del loader de LLM, el de memoria es **default-safe**: si el
bloque ``[memory]`` no trae las keys de decay (config viejo, anterior a
#211), ``load_decay_config()`` devuelve ``DecayConfig()`` con los defaults
de ADR-007 D1 y NO rompe. Solo levanta ``MemoryConfigError`` cuando el
bloque existe pero un valor es invalido (factor > 1, dias <= 0, tipo
erroneo, key extra) o cuando la combinacion de thresholds es incoherente
(``hard_delete_threshold > stale_threshold``).

Este modulo es un sibling de COMPORTAMIENTO de las tablas sagradas
(``semantic``/``episodic``/``procedural``/``audit``): parsea config, no toca
columnas. Queda como punto de extension unico para futuras keys de
``[memory]`` (las 4 de retention de ADR-007 D2, deuda hermana fuera del
scope de #211): un ``RetentionConfig`` futuro vive aca sin re-arquitectura.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# ``config.py`` vive en apps/backend/app/memory/; la raiz del repo esta 4
# niveles arriba (memory -> app -> backend -> apps -> repo root). Mismo
# calculo que ``app/llm/config.py`` (ambos cuelgan de apps/backend/app/<pkg>/).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_PATH = _REPO_ROOT / "ynara.config.json"


class MemoryConfigError(RuntimeError):
    """Config de memoria incoherente o ilegible. Fail-fast, espejo de LlmConfigError."""


class DecayConfig(BaseModel):
    """Thresholds del decay procedural (``ynara.config.json[memory]``, ADR-007 D1).

    Defaults = valores que estaban hardcodeados en ``app/workflows/decay.py``
    antes de #211 (criterio: no alterar comportamiento). ``strict`` +
    ``frozen`` + ``extra='forbid'`` atrapan typos de operador en deploy
    (fail-fast) sin tumbar el worker: el ``try/except`` del task Celery sigue
    siendo la red final.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decay_interval_days: int = Field(default=14, gt=0)
    decay_factor: float = Field(default=0.9, gt=0, le=1)
    stale_threshold: float = Field(default=0.3, gt=0, le=1)
    hard_delete_threshold: float = Field(default=0.1, gt=0, le=1)
    hard_delete_min_days: int = Field(default=90, gt=0)

    @model_validator(mode="after")
    def _check_thresholds_ordered(self) -> DecayConfig:
        """``hard_delete_threshold`` debe quedar bajo ``stale_threshold``.

        Si el umbral de hard-delete queda por encima del de stale, se borrarian
        entradas que nunca llegaron a marcarse stale: rompe la semantica de los
        tres pasos (decay -> stale -> hard-delete). Cross-field que Pydantic no
        valida campo a campo.
        """
        if self.hard_delete_threshold > self.stale_threshold:
            raise ValueError(
                "hard_delete_threshold "
                f"({self.hard_delete_threshold}) no puede superar stale_threshold "
                f"({self.stale_threshold}): rompe la semantica de los 3 pasos del decay"
            )
        return self


def _read_config_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MemoryConfigError(f"no se pudo leer {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MemoryConfigError(f"{path} no es JSON valido: {exc}") from exc
    if not isinstance(data, dict):
        raise MemoryConfigError(f"{path} debe ser un objeto JSON en el top-level")
    return data


# Keys de decay del bloque ``[memory]``. Las demas keys del bloque
# (engine/store/embedding_model/consolidation y las futuras de retention) NO
# pertenecen a ``DecayConfig`` y se ignoran al construirlo (extra='forbid' es
# sobre el sub-conjunto de decay, no sobre todo ``[memory]``).
_DECAY_KEYS = frozenset(DecayConfig.model_fields)


def _build_decay_config(data: dict[str, object]) -> DecayConfig:
    raw_memory = data.get("memory")
    # Bloque [memory] ausente o no-dict -> defaults (compat con config viejo).
    if not isinstance(raw_memory, dict):
        return DecayConfig()

    # Solo las keys de decay; el resto del bloque [memory] no es asunto nuestro.
    decay_values = {key: value for key, value in raw_memory.items() if key in _DECAY_KEYS}
    # Ninguna key de decay presente -> defaults (config viejo, pre-#211).
    if not decay_values:
        return DecayConfig()

    try:
        return DecayConfig.model_validate(decay_values)
    except ValidationError as exc:
        # Envolvemos para que el caller solo atrape MemoryConfigError.
        raise MemoryConfigError(f"ynara.config.json[memory] invalido: {exc}") from exc


def load_decay_config(*, config_path: Path | None = None) -> DecayConfig:
    """Carga y valida los thresholds de decay de ``ynara.config.json[memory]``.

    Inyectable para tests (``config_path``); sin argumentos usa
    ``ynara.config.json`` de la raiz del repo y cachea el resultado. Es
    default-safe: si el bloque ``[memory]`` no trae las keys de decay devuelve
    ``DecayConfig()`` (defaults de ADR-007 D1) y NO rompe.
    """
    if config_path is None:
        return _load_cached()
    return _build_decay_config(_read_config_file(config_path))


@lru_cache(maxsize=1)
def _load_cached() -> DecayConfig:
    return _build_decay_config(_read_config_file(_CONFIG_PATH))
