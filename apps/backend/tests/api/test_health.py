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
from app.api.v1.health import DependencyCheck, readiness
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


async def test_readiness_error_is_class_name_not_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    # El error reportado es el nombre de la clase, jamás el connection string.
    async def fake_db() -> DependencyCheck:
        return _fail()

    async def fake_redis() -> DependencyCheck:
        return _ok()

    monkeypatch.setattr(health, "check_database", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    body = await readiness(Response())
    assert body.checks["database"].error == "ConnectionError"
    assert "://" not in (body.checks["database"].error or "")
