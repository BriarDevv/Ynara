"""Tests E2E del registro de device tokens ``/v1/devices`` (PR-B).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
``test_events.py``: ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` + override de
``get_db``.

Cubre:
1. POST /devices → 201 con el ``DeviceTokenOut`` (sin user_id) en alta nueva.
2. POST /devices del mismo token → 200 (re-registro, upsert).
3. DELETE /devices con body {token} → 204; la fila se borra.
4. DELETE de un token ajeno/inexistente → 404 (sin oráculo).
5. sin token → 401.
6. body inválido (platform fuera del enum / token vacío / extra) → 422.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.device_token import DeviceToken
from app.models.user import User
from app.services.devices import MAX_DEVICE_TOKENS_PER_USER

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _count_tokens(session: AsyncSession, *, token: str) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(DeviceToken).where(DeviceToken.token == token)
        )
    ) or 0


# ---------------------------------------------------------------------------
# 1 + 2. POST register (201 alta / 200 re-registro)
# ---------------------------------------------------------------------------


async def test_register_device_201_new(db_session: AsyncSession) -> None:
    """POST nuevo → 201 con el DeviceTokenOut; user_id no se filtra."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "ios", "token": "tok-1"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["platform"] == "ios"
        assert body["token"] == "tok-1"
        assert set(body.keys()) == {"id", "platform", "token", "last_seen_at"}
        assert "user_id" not in body
        assert str(user.id) not in resp.text
    finally:
        app.dependency_overrides.clear()


async def test_register_device_200_reregister(db_session: AsyncSession) -> None:
    """POST del MISMO token → 200 (re-registro/upsert), sin duplicar la fila."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            first = await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "ios", "token": "tok-dup"},
            )
            second = await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "android", "token": "tok-dup"},
            )

        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["platform"] == "android"
        assert await _count_tokens(db_session, token="tok-dup") == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3 + 4. DELETE by body (204 / 404 sin oráculo)
# ---------------------------------------------------------------------------


async def test_unregister_device_204(db_session: AsyncSession) -> None:
    """DELETE con body {token} → 204; la fila se borra."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "web", "token": "to-del"},
            )
            resp = await client.request(
                "DELETE",
                "/v1/devices",
                headers=_bearer(user.id),
                json={"token": "to-del"},
            )

        assert resp.status_code == 204
        assert resp.content == b""
        assert await _count_tokens(db_session, token="to-del") == 0
    finally:
        app.dependency_overrides.clear()


async def test_unregister_other_users_token_404(db_session: AsyncSession) -> None:
    """DELETE de un token ajeno → 404 (sin oráculo); no borra la fila del owner."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            await client.post(
                "/v1/devices",
                headers=_bearer(owner.id),
                json={"platform": "ios", "token": "owned-tok"},
            )
            resp = await client.request(
                "DELETE",
                "/v1/devices",
                headers=_bearer(intruder.id),
                json={"token": "owned-tok"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "device token no encontrado"
        assert await _count_tokens(db_session, token="owned-tok") == 1
    finally:
        app.dependency_overrides.clear()


async def test_unregister_nonexistent_token_404(db_session: AsyncSession) -> None:
    """DELETE de un token inexistente → MISMO 404 que el ajeno."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.request(
                "DELETE",
                "/v1/devices",
                headers=_bearer(user.id),
                json={"token": "ghost"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "device token no encontrado"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4-bis. cap por usuario → 429 (MED-03)
# ---------------------------------------------------------------------------


async def test_register_over_cap_429(db_session: AsyncSession) -> None:
    """Registrar más de ``MAX_DEVICE_TOKENS_PER_USER`` tokens NUEVOS → 429; re-registro OK."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            for i in range(MAX_DEVICE_TOKENS_PER_USER):
                ok = await client.post(
                    "/v1/devices",
                    headers=_bearer(user.id),
                    json={"platform": "ios", "token": f"tok-{i}"},
                )
                assert ok.status_code == 201

            # El siguiente token NUEVO cruza el cap → 429 con detail genérico.
            over = await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "ios", "token": "tok-over"},
            )
            assert over.status_code == 429
            # regla #4: el detail es genérico, no filtra el token.
            assert "tok-over" not in over.text

            # Re-registrar uno ya propio (upsert) sigue OK aun en el cap (no cuenta).
            re = await client.post(
                "/v1/devices",
                headers=_bearer(user.id),
                json={"platform": "android", "token": "tok-0"},
            )
            assert re.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. sin token → 401
# ---------------------------------------------------------------------------


async def test_devices_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en register y unregister."""
    client = await _client(db_session)
    try:
        async with client:
            r_post = await client.post("/v1/devices", json={"platform": "ios", "token": "x"})
            r_del = await client.request("DELETE", "/v1/devices", json={"token": "x"})
        assert r_post.status_code == 401
        assert r_del.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. body inválido → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_body",
    [
        {"platform": "blackberry", "token": "x"},  # platform fuera del enum
        {"platform": "ios", "token": ""},  # token vacío
        {"platform": "ios"},  # falta token
        {"platform": "ios", "token": "x", "sneaky": True},  # extra=forbid
    ],
)
async def test_register_device_invalid_body_422(
    db_session: AsyncSession, bad_body: dict[str, object]
) -> None:
    """platform inválida / token vacío o faltante / extra → 422."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/devices", headers=_bearer(user.id), json=bad_body)
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
