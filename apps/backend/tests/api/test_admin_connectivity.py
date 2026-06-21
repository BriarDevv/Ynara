"""Tests de INTEGRACIÓN de ``GET /v1/admin/connectivity`` (control plane del panel).

Cubren: (1) el gate de admin (sin token / no-admin -> 401, admin -> 200) igual que
el resto de ``/v1/admin/*``; (2) la degradación elegante del probe de Tailscale
cuando el binario no está disponible -> ``up=False`` y sin targets; (3) el armado
de las URLs para compartir cuando el tailnet está arriba (monkeypatch del probe,
sin depender de un Tailscale real).

Setup espejado de ``test_admin_auth.py`` (``httpx.AsyncClient`` + ``ASGITransport``,
override de ``get_db``, JWT vía ``create_access_token``). El endpoint es read-only:
no commitea, así que el rollback del fixture ``db_session`` limpia lo sembrado.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import connectivity as conn_module
from app.core.deps import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.admin_api import ConnectivityOut, TailscaleStatus

pytestmark = pytest.mark.integration

_PATH = "/v1/admin/connectivity"


async def _seed_user(session: AsyncSession, *, is_admin: bool) -> User:
    """Inserta un User (admin o no) y hace flush para que tenga id asignado."""
    user = User(is_admin=is_admin)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Overridea ``get_db`` con el ``db_session`` del fixture y devuelve el cliente ASGI."""

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_connectivity_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header -> 401 (``get_current_user``)."""
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(_PATH)
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_connectivity_non_admin_401(db_session: AsyncSession) -> None:
    """Un user válido pero NO admin -> 401 (``get_current_admin``)."""
    user = await _seed_user(db_session, is_admin=False)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(_PATH, headers=_bearer(user.id))
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_connectivity_admin_degrades_without_tailscale(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Admin -> 200 con schema válido; sin Tailscale el probe degrada (up=False, sin targets).

    Forzamos el caso "no instalado" (independiente de si la máquina tiene o no
    Tailscale) parcheando el probe; valida la rama de degradación elegante.
    """

    async def _fake_probe(*_args: object, **_kwargs: object) -> TailscaleStatus:
        return TailscaleStatus(up=False, detail="not_installed")

    monkeypatch.setattr(conn_module, "_probe_tailscale", _fake_probe)
    admin = await _seed_user(db_session, is_admin=True)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(_PATH, headers=_bearer(admin.id))
        assert resp.status_code == 200
        data = ConnectivityOut.model_validate(resp.json())
        assert data.tailscale.up is False
        assert data.targets == []
    finally:
        app.dependency_overrides.clear()


async def test_connectivity_builds_targets_when_tailnet_up(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con el tailnet arriba, arma las 2 URLs (Ollama /v1 + Open WebUI) con el IP del tailnet."""

    async def _fake_probe(*_args: object, **_kwargs: object) -> TailscaleStatus:
        return TailscaleStatus(up=True, hostname="lonchos", tailnet_ip="100.64.0.1", detail="up")

    monkeypatch.setattr(conn_module, "_probe_tailscale", _fake_probe)
    admin = await _seed_user(db_session, is_admin=True)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(_PATH, headers=_bearer(admin.id))
        assert resp.status_code == 200
        data = ConnectivityOut.model_validate(resp.json())
        assert data.tailscale.up is True
        assert data.tailscale.tailnet_ip == "100.64.0.1"
        assert len(data.targets) == 2
        api_target = next(t for t in data.targets if t.port == 11434)
        chat_target = next(t for t in data.targets if t.port == 3001)
        assert api_target.url == "http://100.64.0.1:11434/v1"
        assert chat_target.url == "http://100.64.0.1:3001"
    finally:
        app.dependency_overrides.clear()
