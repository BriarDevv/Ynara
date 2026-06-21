"""Tests del ``SecurityHeadersMiddleware`` (``app/main.py``).

Golpea la app real vía ``httpx.AsyncClient`` + ``ASGITransport`` sobre el
endpoint de liveness ``GET /v1/health`` —barato, sin DB ni Redis— para no
depender del lifespan ni de servicios externos (NO ``integration``).

Cubre:
- Los 3 headers base (``X-Content-Type-Options`` / ``X-Frame-Options`` /
  ``Referrer-Policy``) presentes con su valor exacto en cualquier environment.
- HSTS AUSENTE cuando ``environment != "production"``.
- HSTS PRESENTE (max-age >= 1 año + includeSubDomains) cuando production,
  parcheando ``app.main.get_settings`` (el middleware lo lee por request).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport

from app import main
from app.main import app

_HEALTH_URL = "http://test/v1/health"


async def _client() -> AsyncIterator[httpx.AsyncClient]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_base_security_headers_present() -> None:
    """Los 3 headers base van en toda respuesta, con el valor exacto."""
    async for client in _client():
        resp = await client.get(_HEALTH_URL)

    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


async def test_hsts_absent_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """En environment != production NO se emite ``Strict-Transport-Security``."""
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="development"))

    async for client in _client():
        resp = await client.get(_HEALTH_URL)

    assert resp.status_code == 200
    assert "Strict-Transport-Security" not in resp.headers
    # Los base siguen presentes en dev.
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


async def test_hsts_present_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """En production se emite HSTS con max-age >= 1 año + includeSubDomains."""
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="production"))

    async for client in _client():
        resp = await client.get(_HEALTH_URL)

    assert resp.status_code == 200
    hsts = resp.headers["Strict-Transport-Security"]
    assert "includeSubDomains" in hsts
    # max-age en segundos; 1 año = 31_536_000s. Aceptamos cualquier valor >= 1 año.
    max_age = next(
        int(part.split("=", 1)[1])
        for part in (p.strip() for p in hsts.split(";"))
        if part.startswith("max-age=")
    )
    assert max_age >= 31_536_000
