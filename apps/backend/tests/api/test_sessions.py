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
8. Rate-limit (issue #208): N+1 GET del mismo user → 429 + Retry-After; dentro del
   umbral las 3 rutas siguen 200; fail-open (store degradado) nunca da 429 espurio;
   bucket compartido (list+get+close cuentan juntos).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_token_store
from app.core.security import create_access_token
from app.core.token_store import InMemoryTokenStore, RedisTokenStore, TokenStore
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


async def _client(
    db_session: AsyncSession, *, store: TokenStore | None = None
) -> httpx.AsyncClient:
    """Overridea ``get_db`` con el ``db_session`` del fixture y devuelve el cliente.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides
    después vía ``app.dependency_overrides.clear()`` en su ``finally``.

    ``store`` (issue #208): el ``TokenStore`` del rate-limit. Por default NO se
    overridea ``get_token_store`` (usa el ``InMemoryTokenStore`` sin freno efectivo
    del conftest); los tests de rate-limit pasan el suyo para forzar un threshold
    chico o un store que degrada (fail-open).
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    if store is not None:
        app.dependency_overrides[get_token_store] = lambda: store
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _sessions_ratelimit_settings(*, sessions_max: int) -> Settings:
    """Settings determinista para los tests de rate-limit de sessions (threshold chico)."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod",
        SESSIONS_MAX_REQUESTS=sessions_max,
        SESSIONS_WINDOW_SECONDS=60,
    )


class _BoomRedisClient:
    """Cliente Redis que lanza en toda op: ejercita el fail-open del store."""

    async def eval(self, *a: object, **k: object) -> int:
        raise RuntimeError("redis down")

    async def exists(self, *a: object) -> int:
        raise RuntimeError("redis down")

    async def set(self, *a: object, **k: object) -> None:
        raise RuntimeError("redis down")

    async def mget(self, *a: object) -> list[None]:
        raise RuntimeError("redis down")

    async def delete(self, *a: object) -> None:
        raise RuntimeError("redis down")


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


# ---------------------------------------------------------------------------
# 8. Rate-limit por user_id (issue #208): 429, dentro del umbral, fail-open,
#    bucket compartido entre las 3 rutas.
# ---------------------------------------------------------------------------


async def test_sessions_rate_limit_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N+1 GET /sessions del mismo user → 429 con Retry-After (mismo shape que auth).

    Bucket por user_id: con sessions_max=2, 2 GET OK y el 3ro da 429 ANTES de tocar
    la DB. ``detail`` neutro (regla #4); ``Retry-After`` == la ventana.
    """
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=2),
    )
    monkeypatch.setattr(
        "app.api.v1.sessions.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=2),
    )
    user = await _seed_user(db_session)

    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            for _ in range(2):
                ok = await client.get("/v1/sessions", headers=_bearer(user.id))
                assert ok.status_code == 200
            # El 3ro cruza el techo → 429.
            r429 = await client.get("/v1/sessions", headers=_bearer(user.id))
        assert r429.status_code == 429
        assert "demasiados" in r429.json()["detail"]
        assert r429.headers.get("Retry-After") == "60"
    finally:
        app.dependency_overrides.clear()


async def test_sessions_rate_limit_within_threshold_200(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dentro del umbral las 3 rutas (list/get/close) siguen respondiendo 200."""
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=10),
    )
    monkeypatch.setattr(
        "app.api.v1.sessions.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=10),
    )
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            r_list = await client.get("/v1/sessions", headers=_bearer(user.id))
            r_get = await client.get(f"/v1/sessions/{cs.id}", headers=_bearer(user.id))
            r_close = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))
        assert r_list.status_code == 200
        assert r_get.status_code == 200
        assert r_close.status_code == 200
    finally:
        # El close commitea, pero el fixture ``db_session`` usa el patrón savepoint:
        # el rollback de la transacción externa descarta TODO (incluido ese commit),
        # así que no hace falta limpieza manual.
        app.dependency_overrides.clear()


async def test_sessions_rate_limit_fail_open(db_session: AsyncSession) -> None:
    """Con un store que degrada (Redis caído), /sessions NO se bloquea (fail-open).

    El RedisTokenStore que envuelve un cliente que lanza atrapa: ``incr_with_ttl``
    => 0 (no bloquea). Muchos GET seguidos siguen dando 200, nunca un 429 espurio.
    """
    user = await _seed_user(db_session)

    store = RedisTokenStore(_BoomRedisClient())
    client = await _client(db_session, store=store)
    try:
        async with client:
            for _ in range(5):
                resp = await client.get("/v1/sessions", headers=_bearer(user.id))
                assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


async def test_sessions_rate_limit_shared_bucket_across_routes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """list + get + close cuentan en el MISMO bucket por user_id (techo único).

    Con sessions_max=2: el primer GET /sessions y el GET /sessions/{id} consumen el
    bucket; el POST .../close (3ra request) ya cruza el techo → 429.
    """
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=2),
    )
    monkeypatch.setattr(
        "app.api.v1.sessions.get_settings",
        lambda: _sessions_ratelimit_settings(sessions_max=2),
    )
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.ESTUDIO)

    store = InMemoryTokenStore()
    client = await _client(db_session, store=store)
    try:
        async with client:
            r1 = await client.get("/v1/sessions", headers=_bearer(user.id))
            r2 = await client.get(f"/v1/sessions/{cs.id}", headers=_bearer(user.id))
            # 3ra request en el mismo bucket (otra ruta) → 429.
            r3 = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
    finally:
        app.dependency_overrides.clear()
