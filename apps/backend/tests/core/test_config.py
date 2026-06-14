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


def test_prod_rejects_cors_ipv6_loopback() -> None:
    """En production un origin IPv6 loopback (``[::1]``) en CORS rompe el boot.

    ``urlsplit('http://[::1]:3000').hostname`` == ``'::1'``, que está en
    ``dev_hosts`` — el origin IPv6 de dev no debe colarse en prod.
    """
    overrides = {**_PROD_CLEAN, "cors_origins": ["http://[::1]:3000"]}
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(**overrides)


def test_prod_rejects_empty_cors() -> None:
    """En production un CORS vacío (lista vacía) rompe el boot (fail-fast).

    ``any(...)`` sobre lista vacía es False, así que sin el chequeo previo el boot
    pasaría con CERO origins (mala config: API sin política CORS).
    """
    overrides = {**_PROD_CLEAN, "cors_origins": []}
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


# ---------------------------------------------------------------------------
# CORS_ORIGINS por env var (CSV human-friendly, mismo patrón que TRUSTED_PROXY_IPS)
# ---------------------------------------------------------------------------


def test_cors_origins_parsed_from_env_csv() -> None:
    """``CORS_ORIGINS`` CSV desde env se splittea a lista (no crashea por JSON-decode)."""
    s = _settings(CORS_ORIGINS="https://a.com,https://b.com")
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_csv_strips_whitespace() -> None:
    """Espacios alrededor de cada origin del CSV se recortan."""
    s = _settings(CORS_ORIGINS=" https://a.com , https://b.com ")
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_empty_env_falls_back_to_empty_list() -> None:
    """``CORS_ORIGINS=`` (vacío) no crashea el boot; queda lista vacía (mismo
    contrato que ``TRUSTED_PROXY_IPS`` vacío)."""
    s = _settings(CORS_ORIGINS="")
    assert s.cors_origins == []


def test_cors_origins_json_list_passes_intact() -> None:
    """Una lista ya parseada por kwarg pasa intacta (no rompe los tests que usan
    ``cors_origins=[...]``)."""
    s = _settings(cors_origins=["https://app.ynara.com"])
    assert s.cors_origins == ["https://app.ynara.com"]


def test_cors_origins_default_dev_localhost_when_unset() -> None:
    """Sin ``CORS_ORIGINS``, el default dev (localhost:3000/8081) queda intacto."""
    s = _settings(environment="development")
    assert s.cors_origins == ["http://localhost:3000", "http://localhost:8081"]


def test_prod_rejects_cors_localhost_from_env() -> None:
    """El fail-fast de prod rechaza localhost cuando ``CORS_ORIGINS`` llega por env
    (string CSV), no solo por kwarg list."""
    overrides = {**_PROD_CLEAN}
    overrides.pop("cors_origins")
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(CORS_ORIGINS="http://localhost:3000", **overrides)


def test_prod_rejects_empty_cors_from_env() -> None:
    """El fail-fast de prod rechaza ``CORS_ORIGINS=`` (vacío) por env: el split lo
    deja en ``[]`` y el boot no debe pasar con cero origins."""
    overrides = {**_PROD_CLEAN}
    overrides.pop("cors_origins")
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(CORS_ORIGINS="", **overrides)


def test_prod_accepts_cors_real_domains_from_env() -> None:
    """Con dominios reales por env (CSV), production bootea OK."""
    overrides = {**_PROD_CLEAN}
    overrides.pop("cors_origins")
    s = _settings(CORS_ORIGINS="https://app.ynara.com,https://api.ynara.com", **overrides)
    assert s.cors_origins == ["https://app.ynara.com", "https://api.ynara.com"]


# ---------------------------------------------------------------------------
# Fallback de las URLs de Celery hacia redis_url (P2.7)
# ---------------------------------------------------------------------------


def test_celery_urls_default_to_redis_when_unset() -> None:
    """Sin CELERY_*_URL explícitas, broker y result-backend caen a redis_url."""
    s = _settings(REDIS_URL="redis://localhost:6379/3")
    assert s.celery_broker_url == "redis://localhost:6379/3"
    assert s.celery_result_backend == "redis://localhost:6379/3"


def test_celery_urls_respected_when_set() -> None:
    """Con CELERY_*_URL explícitas, se respetan y NO se pisan con redis_url."""
    s = _settings(
        REDIS_URL="redis://localhost:6379/0",
        CELERY_BROKER_URL="redis://broker:6379/1",
        CELERY_RESULT_BACKEND="redis://backend:6379/2",
    )
    assert s.celery_broker_url == "redis://broker:6379/1"
    assert s.celery_result_backend == "redis://backend:6379/2"
