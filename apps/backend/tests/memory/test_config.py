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

from app.memory.config import (
    DecayConfig,
    MemoryConfigError,
    RetentionConfig,
    load_decay_config,
    load_retention_config,
)

# Defaults de ADR-007 D1 (valores que estaban hardcodeados antes de #211).
_DEFAULTS = {
    "decay_interval_days": 14,
    "decay_factor": 0.9,
    "stale_threshold": 0.3,
    "hard_delete_threshold": 0.1,
    "hard_delete_min_days": 90,
}

# Defaults de ADR-007 D2 (valores que estaban hardcodeados en consolidation.py).
_RETENTION_DEFAULTS = {
    "retention_default_days": 365,
    "retention_sensitive_days": 180,
    "retention_sensitive_min_days": 30,
    "retention_sensitive_max_days": 365,
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


def _base_retention(**retention_overrides: Any) -> dict[str, Any]:
    """Bloque ``[memory]`` con las keys no-retention + los dias de retention.

    ``retention_overrides`` reemplaza/agrega keys de retention para los tests de
    fail-fast; sin overrides arma un bloque con los defaults de ADR-007 D2.
    """
    retention = {**_RETENTION_DEFAULTS, **retention_overrides}
    return {
        "memory": {
            "engine": "in-house",
            "store": "postgres-pgvector",
            "embedding_model": "bge-m3",
            "consolidation": "celery-async",
            **retention,
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


# ===========================================================================
# RetentionConfig (ADR-007 D2) — espeja la bateria de DecayConfig
# ===========================================================================


# ---------- Carga OK ----------


def test_load_real_repo_retention_matches_defaults() -> None:
    """El ``ynara.config.json`` real del repo carga y matchea los defaults ADR-007 D2."""
    cfg = load_retention_config()
    assert isinstance(cfg, RetentionConfig)
    assert cfg.retention_default_days == 365
    assert cfg.retention_sensitive_days == 180
    assert cfg.retention_sensitive_min_days == 30
    assert cfg.retention_sensitive_max_days == 365


def test_load_retention_block_with_keys(tmp_path: Path) -> None:
    """Un bloque ``[memory]`` con valores custom de retention se parsea tal cual."""
    path = _write(
        tmp_path, _base_retention(retention_default_days=200, retention_sensitive_days=90)
    )
    cfg = load_retention_config(config_path=path)
    assert cfg.retention_default_days == 200
    assert cfg.retention_sensitive_days == 90
    # Las keys no overrideadas conservan los defaults del bloque.
    assert cfg.retention_sensitive_min_days == 30


# ---------- Default-safe (compat config viejo) ----------


def test_missing_memory_block_uses_retention_defaults(tmp_path: Path) -> None:
    """Sin bloque ``[memory]`` -> RetentionConfig por defaults, NO rompe."""
    path = _write(tmp_path, {"version": "0.1.0"})
    cfg = load_retention_config(config_path=path)
    assert cfg == RetentionConfig()
    assert cfg.retention_default_days == 365
    assert cfg.retention_sensitive_days == 180


def test_memory_block_without_retention_keys_uses_defaults(tmp_path: Path) -> None:
    """``[memory]`` presente pero sin keys de retention -> defaults (config pre-D2)."""
    path = _write(
        tmp_path,
        {
            "memory": {
                "engine": "in-house",
                # Solo keys de decay: ninguna de retention.
                "decay_interval_days": 14,
            }
        },
    )
    cfg = load_retention_config(config_path=path)
    assert cfg == RetentionConfig()


def test_partial_retention_keys_fill_with_defaults(tmp_path: Path) -> None:
    """Solo una key de retention presente -> esa se respeta, el resto por default."""
    path = _write(
        tmp_path,
        {
            "memory": {
                "engine": "in-house",
                "retention_sensitive_days": 120,
            }
        },
    )
    cfg = load_retention_config(config_path=path)
    assert cfg.retention_sensitive_days == 120
    assert cfg.retention_default_days == 365


# ---------- Fail-fast ----------


def test_retention_default_days_zero_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, _base_retention(retention_default_days=0))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_retention_config(config_path=path)


def test_retention_sensitive_days_not_int_raises(tmp_path: Path) -> None:
    """strict=True rechaza un float donde se espera int."""
    path = _write(tmp_path, _base_retention(retention_sensitive_days=180.5))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_retention_config(config_path=path)


def test_retention_sensitive_max_above_365_raises(tmp_path: Path) -> None:
    """El cap de ADR-007 D2 (<=365) sobre el max sensible se enforcea."""
    path = _write(tmp_path, _base_retention(retention_sensitive_max_days=400))
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_retention_config(config_path=path)


def test_retention_sensitive_min_above_max_raises(tmp_path: Path) -> None:
    """``min > max`` rompe la coherencia del rango sensible (cross-field)."""
    path = _write(
        tmp_path,
        _base_retention(retention_sensitive_min_days=200, retention_sensitive_max_days=100),
    )
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_retention_config(config_path=path)


def test_retention_sensitive_default_outside_range_raises(tmp_path: Path) -> None:
    """``sensitive`` fuera de ``[min, max]`` es incoherente (cross-field)."""
    path = _write(
        tmp_path,
        _base_retention(
            retention_sensitive_days=20,
            retention_sensitive_min_days=30,
            retention_sensitive_max_days=365,
        ),
    )
    with pytest.raises(MemoryConfigError, match="invalido"):
        load_retention_config(config_path=path)


def test_non_retention_key_in_memory_block_ignored(tmp_path: Path) -> None:
    """Una key ajena al sub-conjunto de retention (typo) se ignora al construir."""
    data = _base_retention()
    data["memory"]["retention_defualt_days"] = 365  # typo intencional
    path = _write(tmp_path, data)
    cfg = load_retention_config(config_path=path)
    assert cfg == RetentionConfig()


def test_retentionconfig_rejects_extra_field_directly() -> None:
    """``extra='forbid'`` en el modelo rechaza campos no declarados."""
    with pytest.raises(ValueError, match=r"forbidden|extra"):
        RetentionConfig.model_validate({**_RETENTION_DEFAULTS, "retention_defualt_days": 365})


def test_retention_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "ynara.config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MemoryConfigError, match="JSON"):
        load_retention_config(config_path=path)


def test_retention_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "no-existe.json"
    with pytest.raises(MemoryConfigError, match="no se pudo leer"):
        load_retention_config(config_path=path)
