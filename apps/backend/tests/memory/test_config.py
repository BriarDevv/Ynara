"""Tests de carga y fail-fast de ``load_decay_config`` (#211, ADR-007 D1).

Cubren la carga OK contra el ``ynara.config.json`` real del repo (matchea los
defaults de ADR-007 D1), el comportamiento default-safe cuando el bloque
``[memory]`` o las keys de decay faltan (config viejo), y cada caso invalido
que debe disparar ``MemoryConfigError``: factor fuera de rango, threshold <= 0,
cross-field ``hard_delete_threshold > stale_threshold``, dias <= 0 o no-int, y
key extra (``extra='forbid'``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.memory.config import DecayConfig, MemoryConfigError, load_decay_config

# Defaults de ADR-007 D1 (valores que estaban hardcodeados antes de #211).
_DEFAULTS = {
    "decay_interval_days": 14,
    "decay_factor": 0.9,
    "stale_threshold": 0.3,
    "hard_delete_threshold": 0.1,
    "hard_delete_min_days": 90,
}


def _base_memory(**decay_overrides: Any) -> dict[str, Any]:
    """Bloque ``[memory]`` con las keys no-decay + los thresholds de decay.

    ``decay_overrides`` reemplaza/ agrega keys de decay para los tests de
    fail-fast; sin overrides arma un bloque con los defaults.
    """
    decay = {**_DEFAULTS, **decay_overrides}
    return {
        "memory": {
            "engine": "in-house",
            "store": "postgres-pgvector",
            "embedding_model": "bge-m3",
            "consolidation": "celery-async",
            **decay,
        }
    }


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "ynara.config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------- Carga OK ----------


def test_load_real_repo_config_matches_defaults() -> None:
    """El ``ynara.config.json`` real del repo carga y matchea los defaults ADR-007 D1."""
    cfg = load_decay_config()
    assert isinstance(cfg, DecayConfig)
    assert cfg.decay_interval_days == 14
    assert cfg.decay_factor == pytest.approx(0.9)
    assert cfg.stale_threshold == pytest.approx(0.3)
    assert cfg.hard_delete_threshold == pytest.approx(0.1)
    assert cfg.hard_delete_min_days == 90


def test_load_block_with_decay_keys(tmp_path: Path) -> None:
    """Un bloque ``[memory]`` con valores custom se parsea tal cual."""
    path = _write(tmp_path, _base_memory(decay_interval_days=7, decay_factor=0.5))
    cfg = load_decay_config(config_path=path)
    assert cfg.decay_interval_days == 7
    assert cfg.decay_factor == pytest.approx(0.5)
    # Las keys no overrideadas conservan los defaults del bloque.
    assert cfg.stale_threshold == pytest.approx(0.3)


# ---------- Default-safe (compat config viejo) ----------


def test_missing_memory_block_uses_defaults(tmp_path: Path) -> None:
    """Sin bloque ``[memory]`` -> DecayConfig por defaults, NO rompe."""
    path = _write(tmp_path, {"version": "0.1.0"})
    cfg = load_decay_config(config_path=path)
    assert cfg == DecayConfig()
    assert cfg.decay_interval_days == 14


def test_memory_block_without_decay_keys_uses_defaults(tmp_path: Path) -> None:
    """``[memory]`` presente pero sin keys de decay -> defaults (config pre-#211)."""
    path = _write(
        tmp_path,
        {
            "memory": {
                "engine": "in-house",
                "store": "postgres-pgvector",
                "embedding_model": "bge-m3",
                "consolidation": "celery-async",
            }
        },
    )
    cfg = load_decay_config(config_path=path)
    assert cfg == DecayConfig()


def test_partial_decay_keys_fill_with_defaults(tmp_path: Path) -> None:
    """Solo una key de decay presente -> esa se respeta, el resto por default."""
    path = _write(
        tmp_path,
        {
            "memory": {
                "engine": "in-house",
                "decay_interval_days": 30,
            }
        },
    )
    cfg = load_decay_config(config_path=path)
    assert cfg.decay_interval_days == 30
    assert cfg.decay_factor == pytest.approx(0.9)


# ---------- Fail-fast ----------


def test_decay_factor_above_one_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_memory(decay_factor=1.5))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_decay_config(config_path=path)


def test_stale_threshold_zero_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_memory(stale_threshold=0))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_decay_config(config_path=path)


def test_hard_delete_above_stale_raises_cross_field(tmp_path: Path) -> None:
    """``hard_delete_threshold > stale_threshold`` rompe la semantica de los 3 pasos."""
    path = _write(tmp_path, _base_memory(hard_delete_threshold=0.5, stale_threshold=0.3))
    with pytest.raises(MemoryConfigError, match="semantica de los 3 pasos"):
        load_decay_config(config_path=path)


def test_decay_interval_days_zero_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_memory(decay_interval_days=0))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_decay_config(config_path=path)


def test_decay_interval_days_not_int_raises(tmp_path: Path) -> None:
    """strict=True rechaza un float donde se espera int."""
    path = _write(tmp_path, _base_memory(decay_interval_days=14.5))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_decay_config(config_path=path)


def test_non_decay_key_in_memory_block_ignored(tmp_path: Path) -> None:
    """Una key ajena al sub-conjunto de decay (p.ej. un typo) se ignora.

    El loader filtra el bloque ``[memory]`` a las keys de decay conocidas, asi
    que ``decay_facter`` (typo, no es key de decay) NO llega a ``DecayConfig``
    y el resto de keys reales aplica normal. El fail-fast por ``extra='forbid'``
    se cubre construyendo el modelo directo (``test_decayconfig_rejects_extra``).
    """
    data = _base_memory()
    data["memory"]["decay_facter"] = 0.9  # typo intencional, no es key de decay
    path = _write(tmp_path, data)
    cfg = load_decay_config(config_path=path)
    assert cfg == DecayConfig()


def test_decayconfig_rejects_extra_field_directly() -> None:
    """``extra='forbid'`` en el modelo rechaza campos no declarados."""
    with pytest.raises(ValueError, match=r"forbidden|extra"):
        DecayConfig.model_validate({**_DEFAULTS, "decay_facter": 0.9})


def test_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "ynara.config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MemoryConfigError, match="JSON"):
        load_decay_config(config_path=path)


def test_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "no-existe.json"
    with pytest.raises(MemoryConfigError, match="no se pudo leer"):
        load_decay_config(config_path=path)
