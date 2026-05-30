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
    s = _settings(environment="production", JWT_SECRET="x" * 40)
    assert s.environment == "production"
