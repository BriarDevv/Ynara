"""Tests E2E de ``PATCH /v1/users/me`` (update parcial del perfil propio).

``integration`` (tocan la DB de tests dedicada vía ``db_session``): el endpoint
COMMITEA, así que el patrón es el de ``test_sessions_close.py`` — el savepoint
del fixture revierte todo al final. Auth con un JWT real (``create_access_token``)
para el ``user_id`` sembrado; el ``InMemoryTokenStore`` del conftest cubre la
blocklist.

Cubre:
1. PATCH actualiza los 3 campos y persiste en la fila.
2. PATCH parcial NO toca los campos no enviados.
3. PATCH sin token → 401.
4. ``retention_sensitive_days`` fuera de rango (30-365) → 422.
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


async def _seed_user(session: AsyncSession, **fields: object) -> User:
    """Inserta un User (flush, sin commit) para que tenga id y sea visible."""
    user = User(**fields)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Cliente con ``get_db`` overrideado al ``db_session`` del fixture.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides en su
    ``finally`` con ``app.dependency_overrides.clear()``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_patch_updates_own_profile(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, display_name="Mateo")
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                "/v1/users/me",
                headers=_bearer(user.id),
                json={
                    "display_name": "Mateo G",
                    "onboarding_completed": True,
                    "retention_sensitive_days": 90,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Mateo G"
        assert body["onboarding_completed"] is True
        assert body["retention_sensitive_days"] == 90
        assert "password_hash" not in body  # regla #4

        # Persistió en la fila (mismo session overrideado).
        await db_session.refresh(user)
        assert user.display_name == "Mateo G"
        assert user.onboarding_completed is True
        assert user.retention_sensitive_days == 90
    finally:
        app.dependency_overrides.clear()


async def test_patch_partial_leaves_other_fields(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, display_name="Mateo", retention_sensitive_days=180)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                "/v1/users/me",
                headers=_bearer(user.id),
                json={"onboarding_completed": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["onboarding_completed"] is True
        # No enviados → intactos.
        assert body["display_name"] == "Mateo"
        assert body["retention_sensitive_days"] == 180
    finally:
        app.dependency_overrides.clear()


async def test_patch_requires_auth(db_session: AsyncSession) -> None:
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch("/v1/users/me", json={"display_name": "x"})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_patch_rejects_out_of_range_retention(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                "/v1/users/me",
                headers=_bearer(user.id),
                json={"retention_sensitive_days": 10},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_patch_unknown_user_returns_401(db_session: AsyncSession) -> None:
    # Token VÁLIDO para un user_id SIN fila (identidad propia caduca, p.ej. user
    # borrado) → 401 (no 404), mismo criterio que /auth/me. No se siembra el user.
    ghost_id = uuid.uuid4()
    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                "/v1/users/me",
                headers=_bearer(ghost_id),
                json={"display_name": "x"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
