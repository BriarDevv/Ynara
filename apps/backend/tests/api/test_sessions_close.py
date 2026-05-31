"""Tests E2E del endpoint ``POST /v1/sessions/{session_id}/close`` (M10 Ola 2).

Todos son ``integration`` (tocan la DB de tests dedicada: el endpoint hace
``session.commit()``). Ejercitan el stack completo HTTP -> deps con el mismo
patron que ``test_chat.py``:

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, asi
  los asserts consultan la MISMA sesion que commitea el endpoint.

El close NO toca el LLM ni Redis, asi que NO se overridean los clientes Fake (a
diferencia de ``/chat``): solo se necesita el override de ``get_db``.

Limpieza: el endpoint commitea, asi que el rollback del fixture NO alcanza para
los datos persistidos. Cada test borra el ``User`` que sembro al final
(``ON DELETE CASCADE`` arrastra sus ``ChatSession``), dejando la DB idempotente.

Cubre las invariantes del spec: 200 + ``ended_at`` no-null persistido,
idempotencia (cerrar dos veces no mueve el timestamp), aislamiento 404 sin
oraculo (sesion ajena / inexistente), 401 sin token, y preservacion de los
demas campos (``started_at`` / ``mode`` / ``user_id`` intactos).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.enums import Mode
from app.main import app
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User minimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, *, user_id: uuid.UUID, mode: Mode) -> ChatSession:
    """Inserta una ChatSession abierta (``ended_at`` None) para ``user_id``.

    flush (sin commit): el id queda asignado y la fila es visible para el endpoint
    dentro de la misma sesion overrideada; el commit lo hace el propio endpoint.
    """
    cs = ChatSession(user_id=user_id, mode=mode)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Borra el User sembrado (CASCADE arrastra sus ChatSession). Idempotente."""
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
    await session.commit()


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT valido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """Overridea ``get_db`` con el ``db_session`` del fixture y devuelve el cliente.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides
    despues via ``app.dependency_overrides.clear()`` en su ``finally``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Happy path: cerrar propia sesion -> 200, ended_at no-null (respuesta + DB)
# ---------------------------------------------------------------------------


async def test_close_own_session_sets_ended_at(db_session: AsyncSession) -> None:
    """200; ended_at no-null en la respuesta y persistido en la DB."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                f"/v1/sessions/{cs.id}/close",
                headers=_bearer(user.id),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(cs.id)
        assert body["ended_at"] is not None

        # Persistido: re-leemos la fila desde la DB (el endpoint commiteo).
        await db_session.refresh(cs)
        assert cs.ended_at is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Idempotente: cerrar dos veces -> 200 ambas; el ended_at no cambia
# ---------------------------------------------------------------------------


async def test_close_is_idempotent(db_session: AsyncSession) -> None:
    """Cerrar dos veces: ambas 200; el ended_at de la 2da == el de la 1ra."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.ESTUDIO)

    client = await _client(db_session)
    try:
        async with client:
            first = await client.post(
                f"/v1/sessions/{cs.id}/close",
                headers=_bearer(user.id),
            )
            assert first.status_code == 200
            first_ended_at = first.json()["ended_at"]
            assert first_ended_at is not None

            second = await client.post(
                f"/v1/sessions/{cs.id}/close",
                headers=_bearer(user.id),
            )
            assert second.status_code == 200
            second_ended_at = second.json()["ended_at"]

        # El segundo cierre NO movio el timestamp (idempotente).
        assert second_ended_at == first_ended_at
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Aislamiento: sesion de otro user -> 404 (sin oraculo de existencia ajena)
# ---------------------------------------------------------------------------


async def test_close_session_of_other_user_returns_404(db_session: AsyncSession) -> None:
    """Un intruder con el session_id del owner recibe 404 (mismo error)."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=owner.id, mode=Mode.BIENESTAR)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                f"/v1/sessions/{cs.id}/close",
                headers=_bearer(intruder.id),
            )

        assert resp.status_code == 404

        # No se cerro la sesion del owner: ended_at sigue None (sin side-effect).
        await db_session.refresh(cs)
        assert cs.ended_at is None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, owner.id)
        with suppress(Exception):
            await _delete_user(db_session, intruder.id)


# ---------------------------------------------------------------------------
# Sesion inexistente (uuid random) -> 404
# ---------------------------------------------------------------------------


async def test_close_nonexistent_session_returns_404(db_session: AsyncSession) -> None:
    """Un session_id random que no existe da el MISMO 404 que la sesion ajena."""
    user = await _seed_user(db_session)
    nonexistent_id = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                f"/v1/sessions/{nonexistent_id}/close",
                headers=_bearer(user.id),
            )

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Auth: sin token -> 401
# ---------------------------------------------------------------------------


async def test_close_without_token_returns_401(db_session: AsyncSession) -> None:
    """Sin Authorization header -> 401 (get_current_user)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(f"/v1/sessions/{cs.id}/close")

        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Solo lifecycle: cerrar no toca started_at / mode / user_id
# ---------------------------------------------------------------------------


async def test_close_preserves_other_fields(db_session: AsyncSession) -> None:
    """Cerrar setea ended_at pero deja started_at / mode / user_id intactos."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.PRODUCTIVIDAD)
    started_at_before = cs.started_at

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                f"/v1/sessions/{cs.id}/close",
                headers=_bearer(user.id),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == str(user.id)
        assert body["mode"] == Mode.PRODUCTIVIDAD.value
        # started_at intacto: se compara por valor de datetime (no por string,
        # para no atarse al formato exacto de serializacion de Pydantic/Postgres).
        assert datetime.fromisoformat(body["started_at"]) == started_at_before
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)
