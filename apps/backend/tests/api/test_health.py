"""Tests de los endpoints de health (liveness + readiness).

Sin DB ni Redis reales: los checks de readiness (``check_database`` /
``check_redis``) se parchean en el módulo para no tocar servicios externos. El
run default (sin marker ``integration``) queda 100% en memoria.
"""

from __future__ import annotations

import pytest
from fastapi import Response

from app import __version__
from app.api.v1 import health
from app.api.v1.health import DependencyCheck, check_database, check_redis, readiness
from app.api.v1.health import health as liveness


def _ok() -> DependencyCheck:
    return DependencyCheck(ok=True)


def _fail() -> DependencyCheck:
    return DependencyCheck(ok=False, error="ConnectionError")


# ---------- liveness ----------


async def test_liveness_ok() -> None:
    resp = await liveness()
    assert resp.status == "ok"
    assert resp.version == __version__


# ---------- readiness ----------


async def test_readiness_ok_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_db() -> DependencyCheck:
        return _ok()

    async def fake_redis() -> DependencyCheck:
        return _ok()

    monkeypatch.setattr(health, "check_database", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    response = Response()
    body = await readiness(response)

    assert response.status_code == 200
    assert body.status == "ready"
    assert body.checks["database"].ok is True
    assert body.checks["redis"].ok is True


async def test_readiness_db_down_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_db() -> DependencyCheck:
        return _fail()

    async def fake_redis() -> DependencyCheck:
        return _ok()

    monkeypatch.setattr(health, "check_database", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    response = Response()
    body = await readiness(response)

    assert response.status_code == 503
    assert body.status == "degraded"
    assert body.checks["database"].ok is False
    assert body.checks["redis"].ok is True


async def test_readiness_redis_down_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_db() -> DependencyCheck:
        return _ok()

    async def fake_redis() -> DependencyCheck:
        return _fail()

    monkeypatch.setattr(health, "check_database", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    response = Response()
    body = await readiness(response)

    assert response.status_code == 503
    assert body.status == "degraded"


async def test_readiness_both_down_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_db() -> DependencyCheck:
        return _fail()

    async def fake_redis() -> DependencyCheck:
        return _fail()

    monkeypatch.setattr(health, "check_database", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    response = Response()
    body = await readiness(response)

    assert response.status_code == 503
    assert body.status == "degraded"
    assert body.checks["database"].ok is False
    assert body.checks["redis"].ok is False


# ---------- checks reales: no filtran el connection string (regla #2) ----------


class _BoomEngine:
    """Engine falso cuyo connect() falla con un mensaje que incluye el DSN."""

    def connect(self) -> object:
        raise RuntimeError("connect to postgresql+asyncpg://user:s3cret@host:5432/db failed")


class _BoomRedis:
    async def ping(self) -> None:
        raise RuntimeError("Error 111 connecting to redis://:p4ssw0rd@host:6379/0")

    async def aclose(self) -> None:
        return None


async def test_check_database_error_is_class_name_not_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ejercita el path real except->type(exc).__name__: el str(exc) trae el DSN,
    # el reporte no.
    monkeypatch.setattr(health, "engine", _BoomEngine())
    result = await check_database()
    assert result.ok is False
    assert result.error == "RuntimeError"
    assert "s3cret" not in (result.error or "")
    assert "://" not in (result.error or "")


async def test_check_redis_error_is_class_name_not_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health.aioredis, "from_url", lambda *a, **k: _BoomRedis())
    result = await check_redis()
    assert result.ok is False
    assert result.error == "RuntimeError"
    assert "p4ssw0rd" not in (result.error or "")
    assert "://" not in (result.error or "")
