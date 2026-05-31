"""Tests E2E de las read surfaces de ``/v1/sessions`` (list + detail).

Todos son ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Los
GET son **read-only**: NO commitean, así que el rollback del fixture ``db_session``
limpia todo lo sembrado al final de cada test (sin ``_delete_user`` ni commit
manual, a diferencia de ``test_sessions_close.py``, que sí commitea porque el
endpoint de close persiste). La siembra usa ``flush`` (sin commit): el id queda
asignado y la fila es visible para el endpoint dentro de la MISMA sesión
overrideada.

Patrón (igual que ``test_memory.py`` / ``test_sessions_close.py``):

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, así el
  endpoint lee la MISMA sesión donde el test sembró.

El listado NO toca LLM ni Redis, así que NO se overridean los clientes Fake (a
diferencia de ``/chat``): solo se necesita el override de ``get_db``.

Cubre el spec (aislamiento es el test CLAVE):
1. ``GET /sessions`` del user A → solo SUS sesiones, ``total`` correcto, ordenadas.
2. Paginación (limit/offset) correcta.
3. ``GET /sessions/{id}`` propio → 200 con el ``SessionOut``.
4. AISLAMIENTO: ``GET /sessions/{id}`` de OTRO user → 404 (no 200, no leak).
5. ``GET /sessions/{uuid-inexistente}`` → 404 (mismo detail que ajena).
6. ``limit`` fuera de rango (0 / 101) → 422.
7. sin token → 401 (list + detail).
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
from app.enums import Mode
from app.main import app
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers de siembra (flush, NO commit — el rollback del fixture limpia)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, *, user_id: uuid.UUID, mode: Mode) -> ChatSession:
    """Inserta una ChatSession abierta (``ended_at`` None) para ``user_id``.

    flush (sin commit): el id queda asignado y la fila es visible para el endpoint
    dentro de la misma sesión overrideada; los GET no commitean.
    """
    cs = ChatSession(user_id=user_id, mode=mode)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Overridea ``get_db`` con el ``db_session`` del fixture y devuelve el cliente.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides
    después vía ``app.dependency_overrides.clear()`` en su ``finally``.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# 1. GET /sessions del user A → solo SUS sesiones, total correcto, ordenadas
# ---------------------------------------------------------------------------


async def test_list_sessions_only_own_ordered(db_session: AsyncSession) -> None:
    """Lista solo las sesiones de A, ``total`` == 3, ordenadas por started_at DESC."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    # 3 sesiones de A (orden de inserción → started_at ascendente por default now()).
    cs_a1 = await _seed_session(db_session, user_id=user_a.id, mode=Mode.VIDA)
    cs_a2 = await _seed_session(db_session, user_id=user_a.id, mode=Mode.ESTUDIO)
    cs_a3 = await _seed_session(db_session, user_id=user_a.id, mode=Mode.BIENESTAR)
    # 1 sesión de B: NO debe aparecer en el listado de A.
    cs_b = await _seed_session(db_session, user_id=user_b.id, mode=Mode.PRODUCTIVIDAD)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/sessions", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total"}

        # total = conteo del user A (3), no cuenta la de B.
        assert body["total"] == 3
        ids = [it["id"] for it in body["items"]]
        assert len(ids) == 3
        assert str(cs_b.id) not in ids  # aislamiento: nada de B.

        # Solo sesiones de A.
        assert all(it["user_id"] == str(user_a.id) for it in body["items"])

        # Orden started_at DESC: el listado es no-creciente en started_at.
        started = [it["started_at"] for it in body["items"]]
        assert started == sorted(started, reverse=True)
        # Sanity: las 3 ids de A están todas presentes.
        assert {str(cs_a1.id), str(cs_a2.id), str(cs_a3.id)} == set(ids)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. Paginación (limit/offset) correcta
# ---------------------------------------------------------------------------


async def test_list_sessions_paginated(db_session: AsyncSession) -> None:
    """limit/offset paginan; total es el conteo completo y las páginas no se solapan."""
    user = await _seed_user(db_session)
    for _ in range(3):
        await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        async with client:
            # Página 1: limit=2 → 2 items, total=3.
            resp1 = await client.get("/v1/sessions?limit=2&offset=0", headers=_bearer(user.id))
            # Página 2: offset=2 → 1 item restante.
            resp2 = await client.get("/v1/sessions?limit=2&offset=2", headers=_bearer(user.id))

        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["total"] == 3
        assert len(body1["items"]) == 2

        body2 = resp2.json()
        assert body2["total"] == 3
        assert len(body2["items"]) == 1

        # Las dos páginas no se solapan (ids distintos).
        ids_p1 = {it["id"] for it in body1["items"]}
        ids_p2 = {it["id"] for it in body2["items"]}
        assert ids_p1.isdisjoint(ids_p2)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. GET /sessions/{id} propio → 200 SessionOut
# ---------------------------------------------------------------------------


async def test_get_own_session(db_session: AsyncSession) -> None:
    """200 con el SessionOut de la propia sesión (campos del mirror del modelo)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.PRODUCTIVIDAD)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/sessions/{cs.id}", headers=_bearer(user.id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(cs.id)
        assert body["user_id"] == str(user.id)
        assert body["mode"] == Mode.PRODUCTIVIDAD.value
        assert body["ended_at"] is None  # sesión abierta.
        # Metadata del mirror presente.
        assert "started_at" in body
        assert "created_at" in body
        assert "updated_at" in body
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. AISLAMIENTO CLAVE: GET /sessions/{id} de OTRO user → 404 (no 200, no leak)
# ---------------------------------------------------------------------------


async def test_get_other_users_session_returns_404_no_oracle(db_session: AsyncSession) -> None:
    """El detail de la sesión del owner consultado por un intruder da 404 (sin leak).

    Es el test de aislamiento: un GET de la sesión de otro user NUNCA devuelve 200
    ni filtra datos. Mismo 404 (status + detail) que un id inexistente.
    """
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=owner.id, mode=Mode.BIENESTAR)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/sessions/{cs.id}", headers=_bearer(intruder.id))

        assert resp.status_code == 404
        assert resp.json()["detail"] == "sesion no encontrada"
        # El user_id del owner NO se filtra en la respuesta del intruder.
        assert str(owner.id) not in resp.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. GET /sessions/{uuid inexistente} → 404 (mismo detail que ajena)
# ---------------------------------------------------------------------------


async def test_get_nonexistent_session_same_404(db_session: AsyncSession) -> None:
    """Un UUID random inexistente da el MISMO 404 (status + detail) que la ajena."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/sessions/{nonexistent}", headers=_bearer(user.id))

        assert resp.status_code == 404
        assert resp.json()["detail"] == "sesion no encontrada"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. limit fuera de rango (0 / 101) → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_limit", [0, 101])
async def test_list_sessions_limit_out_of_range_422(
    db_session: AsyncSession, bad_limit: int
) -> None:
    """limit=0 o limit=101 → 422 (FastAPI valida el Query ge=1 le=100)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/sessions?limit={bad_limit}", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_list_sessions_negative_offset_422(db_session: AsyncSession) -> None:
    """offset < 0 → 422 (FastAPI valida el Query ge=0)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/sessions?offset=-1", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. sin token → 401 (list + detail)
# ---------------------------------------------------------------------------


async def test_sessions_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en list y en detail (get_current_user)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        async with client:
            r_list = await client.get("/v1/sessions")
            r_detail = await client.get(f"/v1/sessions/{cs.id}")
        assert r_list.status_code == 401
        assert r_detail.status_code == 401
    finally:
        app.dependency_overrides.clear()
