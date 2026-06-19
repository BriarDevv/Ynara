"""Tests de INTEGRACIÓN del gate de admin del panel interno (``/v1/admin/*``).

Cubren el invariante CLAVE de la superficie admin: solo un ``User`` con ``is_admin=True``
(o en ``ADMIN_BOOTSTRAP_IDS``) accede; cualquier otro recibe **401 estático** (mismo
``detail`` que credenciales inválidas, sin oráculo de "existe pero no es admin", regla #4).

Setup espejado de ``tests/api/test_sessions.py`` (``httpx.AsyncClient`` +
``ASGITransport(app=app)``, override de ``get_db`` con el ``db_session`` del fixture,
JWT vía ``create_access_token``). Los 6 GET son read-only: NO commitean, así que el
rollback del fixture ``db_session`` limpia lo sembrado.

Cobertura:
1. Sin token -> 401 (los 6 endpoints, vía ``get_current_user``).
2. Token de un user NO admin -> 401 (``get_current_admin``).
3. Token de un user ``is_admin=True`` -> 200 (los 6 endpoints).
4. El 401 de no-admin tiene el MISMO ``detail`` que un 401 de token inválido (sin oráculo).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.integration

# Los 6 endpoints del panel (los con rango toman el default 7d; /system no toma rango).
_ADMIN_GET_PATHS = [
    "/v1/admin/overview",
    "/v1/admin/users",
    "/v1/admin/modes",
    "/v1/admin/moat",
    "/v1/admin/audit",
    "/v1/admin/system",
]


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


@pytest.mark.parametrize("path", _ADMIN_GET_PATHS)
async def test_admin_without_token_401(db_session: AsyncSession, path: str) -> None:
    """Sin Authorization header -> 401 en los 6 endpoints (``get_current_user``)."""
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(path)
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", _ADMIN_GET_PATHS)
async def test_admin_non_admin_user_401(db_session: AsyncSession, path: str) -> None:
    """Un user válido pero NO admin -> 401 (``get_current_admin``)."""
    user = await _seed_user(db_session, is_admin=False)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(path, headers=_bearer(user.id))
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", _ADMIN_GET_PATHS)
async def test_admin_admin_user_200(db_session: AsyncSession, path: str) -> None:
    """Un user ``is_admin=True`` -> 200 en los 6 endpoints."""
    admin = await _seed_user(db_session, is_admin=True)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(path, headers=_bearer(admin.id))
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


async def test_admin_non_admin_same_detail_as_bad_token(db_session: AsyncSession) -> None:
    """Anti-oráculo (regla #4): un user válido pero NO admin recibe el MISMO 401
    ``detail`` que un token INVÁLIDO (``UNAUTHORIZED_DETAIL``) — no se puede
    distinguir "token válido pero no admin" de "token inválido".

    El caso sin token (``OAuth2PasswordBearer`` con ``auto_error``, detail propio
    de FastAPI) lo cubre ``test_admin_without_token_401``; ese es otro eje (faltan
    credenciales), no un oráculo sobre la condición de admin."""
    user = await _seed_user(db_session, is_admin=False)
    client = await _client(db_session)
    try:
        async with client:
            bad_token = await client.get(
                "/v1/admin/overview",
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
            non_admin = await client.get("/v1/admin/overview", headers=_bearer(user.id))
        assert bad_token.status_code == 401
        assert non_admin.status_code == 401
        assert non_admin.json()["detail"] == bad_token.json()["detail"]
    finally:
        app.dependency_overrides.clear()
