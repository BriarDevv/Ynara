"""Tests del Settings de core/config.py: guardia del JWT secret en production."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "_env_file": None,
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET": "x" * 40,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_dev_allows_weak_secret() -> None:
    # En development el placeholder se permite (sin fricción para dev).
    s = _settings(environment="development", JWT_SECRET="cambiar-en-produccion")
    assert s.jwt_secret == "cambiar-en-produccion"


def test_prod_rejects_placeholder_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        _settings(environment="production", JWT_SECRET="cambiar-en-produccion")


def test_prod_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        _settings(environment="production", JWT_SECRET="corto")


def test_prod_accepts_strong_secret() -> None:
    # Para pasar el validador de dev-config en prod hace falta master key + CORS reales.
    s = _settings(
        environment="production",
        JWT_SECRET="x" * 40,
        cors_origins=["https://app.ynara.com"],
        MEMORY_ENCRYPTION_MASTER_KEY="k" * 44,
    )
    assert s.environment == "production"


# ---------------------------------------------------------------------------
# S5 — fail-fast de config de dev en production (CORS localhost + master key)
# ---------------------------------------------------------------------------

# Config "limpia" de prod reutilizable: master key seteada + CORS de dominio real.
# Los tests sobreescriben SOLO el campo que quieren romper.
_PROD_CLEAN: dict[str, object] = {
    "environment": "production",
    "JWT_SECRET": "x" * 40,
    "MEMORY_ENCRYPTION_MASTER_KEY": "k" * 44,
    "cors_origins": ["https://app.ynara.com"],
}


def test_prod_rejects_cors_localhost() -> None:
    """En production un origin localhost en CORS rompe el boot (fail-fast)."""
    overrides = {**_PROD_CLEAN, "cors_origins": ["http://localhost:3000"]}
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(**overrides)


def test_prod_rejects_cors_127_0_0_1() -> None:
    """En production un origin 127.0.0.1 en CORS también rompe el boot."""
    overrides = {**_PROD_CLEAN, "cors_origins": ["http://127.0.0.1:8081"]}
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(**overrides)


def test_prod_rejects_empty_master_key() -> None:
    """En production una MEMORY_ENCRYPTION_MASTER_KEY vacía rompe el boot."""
    overrides = {**_PROD_CLEAN, "MEMORY_ENCRYPTION_MASTER_KEY": ""}
    with pytest.raises(ValueError, match="MEMORY_ENCRYPTION_MASTER_KEY"):
        _settings(**overrides)


def test_prod_accepts_clean_config() -> None:
    """Con CORS de dominio real + master key seteada, production bootea OK."""
    s = _settings(**_PROD_CLEAN)
    assert s.environment == "production"
    assert s.memory_encryption_master_key == "k" * 44


def test_dev_allows_localhost_cors_and_empty_master_key() -> None:
    """En development el default localhost + master key vacía NO rompen (sin fricción)."""
    # master key EXPLÍCITA "" (no se hereda del ambiente): _env_file=None ignora el
    # archivo .env pero NO las env vars reales del proceso (p.ej. la
    # MEMORY_ENCRYPTION_MASTER_KEY de test que la CI exporta para el cifrado). El
    # kwarg explícito tiene prioridad sobre la env var, así el test queda hermético.
    # cors_origins se omite a propósito: usa el default de dev (localhost).
    s = _settings(environment="development", MEMORY_ENCRYPTION_MASTER_KEY="")
    assert any("localhost" in origin for origin in s.cors_origins)
    assert s.memory_encryption_master_key == ""
