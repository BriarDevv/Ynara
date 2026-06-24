"""Tests E2E del CRUD de ``/v1/tasks`` (dominio TAREAS, Fase D1).

Todos son ``integration`` (tocan la DB de tests dedicada vía ``db_session``). El
patrón es el de ``test_events.py``:

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, así el
  endpoint lee/escribe la MISMA sesión donde el test sembró.

El CRUD NO toca LLM ni Redis, así que NO se overridean los clientes Fake: solo se
necesita el override de ``get_db``. El fixture ``db_session`` usa el patrón savepoint.

A diferencia de Agenda, el CRUD de tareas expone SOLO GET + PATCH (el alta la hace el
agente, no un POST manual). Cubre el spec (aislamiento es el test CLAVE):
1. ``GET /tasks`` del user A → solo SUS tareas, ``total`` correcto, pending primero.
2. ``PATCH /tasks/{id}`` togglea status → devuelve el ``TaskOut`` actualizado.
3. AISLAMIENTO: patch de una tarea ajena → 404 (sin oráculo) == inexistente.
4. sin token → 401.
5. validación de body (status inválido / faltante / extra) → 422.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.enums import TaskStatus
from app.main import app
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate
from app.services.tasks import TaskStore

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers de siembra (flush, NO commit — el savepoint del fixture limpia)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str = "Tarea",
    status: TaskStatus = TaskStatus.PENDING,
    scheduled_at: str | None = None,
    duration_min: int | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        title=title,
        status=status,
        scheduled_at=datetime.fromisoformat(scheduled_at) if scheduled_at else None,
        duration_min=duration_min,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# 1. GET /tasks del user A → solo SUS tareas, total correcto, pending primero
# ---------------------------------------------------------------------------


async def test_list_tasks_only_own_ordered(db_session: AsyncSession) -> None:
    """Lista solo las tareas de A, ``total`` == 3, pending primero + scheduled asc."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    # done (debe ir al final pese a horario temprano).
    t_done = await _seed_task(
        db_session,
        user_id=user_a.id,
        title="Hecha",
        status=TaskStatus.DONE,
        scheduled_at="2026-06-22T06:00:00+00:00",
    )
    t_late = await _seed_task(
        db_session, user_id=user_a.id, title="Tarde", scheduled_at="2026-06-22T18:00:00+00:00"
    )
    t_early = await _seed_task(
        db_session, user_id=user_a.id, title="Temprano", scheduled_at="2026-06-22T08:00:00+00:00"
    )
    # 1 tarea de B: NO debe aparecer.
    t_b = await _seed_task(db_session, user_id=user_b.id, title="De B")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/tasks", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total"}

        # total = conteo del user A (3), no cuenta el de B.
        assert body["total"] == 3
        ids = [it["id"] for it in body["items"]]
        assert len(ids) == 3
        assert str(t_b.id) not in ids  # aislamiento: nada de B.

        # pending primero (Temprano, Tarde por scheduled asc), done al final.
        assert ids == [str(t_early.id), str(t_late.id), str(t_done.id)]

        # TaskOut NO expone user_id / created_at / updated_at.
        item = body["items"][0]
        assert set(item.keys()) == {"id", "title", "status", "scheduled_at", "duration_min"}
    finally:
        app.dependency_overrides.clear()


async def test_list_tasks_empty(db_session: AsyncSession) -> None:
    """Un user sin tareas → 200 con ``{items: [], total: 0}``."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/tasks", headers=_bearer(user.id))

        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1b. Paginación (API-002): limit acota la query, total sigue completo
# ---------------------------------------------------------------------------


async def _seed_three_pending(db_session: AsyncSession, user_id: uuid.UUID) -> None:
    """Siembra 3 tareas pending a horas 8/10/12 (orden estable scheduled asc)."""
    for hour in (8, 10, 12):
        await _seed_task(
            db_session,
            user_id=user_id,
            title=f"T{hour}",
            scheduled_at=f"2026-06-22T{hour:02d}:00:00+00:00",
        )


async def test_list_tasks_respects_limit(db_session: AsyncSession) -> None:
    """``?limit=2`` devuelve 2 items pero ``total`` sigue siendo el conteo completo."""
    user = await _seed_user(db_session)
    await _seed_three_pending(db_session, user.id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/tasks?limit=2", headers=_bearer(user.id))

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3  # total = conteo del user, NO el largo de la página
        # primeras 2 por scheduled asc.
        assert [it["title"] for it in body["items"]] == ["T8", "T10"]
    finally:
        app.dependency_overrides.clear()


async def test_list_tasks_offset_paginates_without_overlap(db_session: AsyncSession) -> None:
    """``limit``+``offset`` pagina con el mismo orden estable, sin solapar páginas."""
    user = await _seed_user(db_session)
    await _seed_three_pending(db_session, user.id)

    client = await _client(db_session)
    try:
        async with client:
            page1 = (
                await client.get("/v1/tasks?limit=2&offset=0", headers=_bearer(user.id))
            ).json()
            page2 = (
                await client.get("/v1/tasks?limit=2&offset=2", headers=_bearer(user.id))
            ).json()

        assert [it["title"] for it in page1["items"]] == ["T8", "T10"]
        assert [it["title"] for it in page2["items"]] == ["T12"]
        ids1 = {it["id"] for it in page1["items"]}
        ids2 = {it["id"] for it in page2["items"]}
        assert ids1.isdisjoint(ids2)  # páginas sucesivas no se solapan
        assert page1["total"] == page2["total"] == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1"])
async def test_list_tasks_pagination_out_of_range_422(db_session: AsyncSession, query: str) -> None:
    """``limit`` fuera de ``[1, 200]`` u ``offset`` negativo → 422 (FastAPI valida)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/tasks?{query}", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. PATCH /tasks/{id} togglea status → devuelve el TaskOut actualizado
# ---------------------------------------------------------------------------


async def test_patch_task_toggles_to_done(db_session: AsyncSession) -> None:
    """PATCH con status=done → 200 con el TaskOut actualizado; user_id no se filtra."""
    user = await _seed_user(db_session)
    task = await _seed_task(db_session, user_id=user.id, status=TaskStatus.PENDING)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/tasks/{task.id}",
                headers=_bearer(user.id),
                json={"status": "done"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == TaskStatus.DONE.value
        assert body["id"] == str(task.id)
        # PATCH devuelve el TaskOut SOLO (no el envelope items/total).
        assert set(body.keys()) == {"id", "title", "status", "scheduled_at", "duration_min"}
        assert "user_id" not in body
        assert str(user.id) not in resp.text

        # Persistido.
        await db_session.refresh(task)
        assert task.status == TaskStatus.DONE
    finally:
        app.dependency_overrides.clear()


async def test_patch_task_reopens_to_pending(db_session: AsyncSession) -> None:
    """PATCH con status=pending re-abre una tarea done (toggle inverso)."""
    user = await _seed_user(db_session)
    task = await _seed_task(db_session, user_id=user.id, status=TaskStatus.DONE)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/tasks/{task.id}",
                headers=_bearer(user.id),
                json={"status": "pending"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == TaskStatus.PENDING.value
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. AISLAMIENTO: patch de tarea ajena → 404 (sin oráculo) == inexistente
# ---------------------------------------------------------------------------


async def test_patch_other_users_task_404_no_oracle(db_session: AsyncSession) -> None:
    """PATCH de una tarea de otro user → 404, sin mutar la fila del owner."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    task = await _seed_task(db_session, user_id=owner.id, status=TaskStatus.PENDING)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/tasks/{task.id}",
                headers=_bearer(intruder.id),
                json={"status": "done"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "tarea no encontrada"
        # No se mutó la tarea del owner.
        await db_session.refresh(task)
        assert task.status == TaskStatus.PENDING
        assert str(owner.id) not in resp.text
    finally:
        app.dependency_overrides.clear()


async def test_patch_nonexistent_task_same_404(db_session: AsyncSession) -> None:
    """PATCH de un UUID inexistente → MISMO 404 (status + detail) que el ajeno."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/tasks/{nonexistent}",
                headers=_bearer(user.id),
                json={"status": "done"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "tarea no encontrada"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. sin token → 401 (todas las rutas)
# ---------------------------------------------------------------------------


async def test_tasks_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en list / patch."""
    user = await _seed_user(db_session)
    task = await _seed_task(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            r_list = await client.get("/v1/tasks")
            r_patch = await client.patch(f"/v1/tasks/{task.id}", json={"status": "done"})
        assert r_list.status_code == 401
        assert r_patch.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. validación de body → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_body",
    [
        {},  # status faltante (requerido).
        {"status": "garbage"},  # status fuera del enum.
        {"status": "done", "title": "x"},  # extra=forbid.
    ],
)
async def test_patch_task_invalid_body_422(
    db_session: AsyncSession, bad_body: dict[str, object]
) -> None:
    """status faltante / inválido / extra → 422."""
    user = await _seed_user(db_session)
    task = await _seed_task(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/tasks/{task.id}", headers=_bearer(user.id), json=bad_body
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Idempotencia: FIX 2 — duration_min es parte de la clave de dedup
# ---------------------------------------------------------------------------


async def test_create_task_dedup_includes_duration_min(db_session: AsyncSession) -> None:
    """FIX 2: un retry con duration_min distinto NO devuelve la primera tarea.

    Antes del fix, ``_find_duplicate`` usaba solo ``(user_id, title, scheduled_at)``,
    así que un retry con ``duration_min`` diferente devolvía silenciosamente la primera
    tarea (corrupción silenciosa). Con el fix, la clave incluye ``duration_min`` y el
    segundo create inserta una fila nueva.
    """
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    payload_30 = TaskCreate(
        title="Dentista",
        scheduled_at=datetime.fromisoformat("2026-06-22T10:00:00+00:00"),
        duration_min=30,
    )
    payload_60 = TaskCreate(
        title="Dentista",
        scheduled_at=datetime.fromisoformat("2026-06-22T10:00:00+00:00"),
        duration_min=60,
    )

    result_30 = await store.create_task(payload_30)
    result_60 = await store.create_task(payload_60)

    # Deben ser dos tareas distintas (diferente id).
    assert result_30["id"] != result_60["id"]
    assert result_30["duration_min"] == 30
    assert result_60["duration_min"] == 60


async def test_create_task_dedup_same_duration_min_returns_existing(
    db_session: AsyncSession,
) -> None:
    """FIX 2 (caso positivo): mismo (title, scheduled_at, duration_min) → devuelve existente.

    La idempotencia ante reintentos con la misma tupla sigue funcionando: un retry con
    TODOS los campos iguales devuelve la tarea original (sin duplicar).
    """
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    payload = TaskCreate(
        title="Dentista",
        scheduled_at=datetime.fromisoformat("2026-06-22T10:00:00+00:00"),
        duration_min=45,
    )

    result_1 = await store.create_task(payload)
    result_2 = await store.create_task(payload)

    # Misma tupla → misma tarea (idempotencia preservada).
    assert result_1["id"] == result_2["id"]


async def test_create_task_dedup_null_duration_min_is_part_of_key(
    db_session: AsyncSession,
) -> None:
    """FIX 2 (NULL): duration_min NULL vs. un valor concreto son claves distintas.

    Una tarea sin duración y una con duración=30 y el mismo título/horario NO deben
    deduplicarse (son tareas semánticamente diferentes).
    """
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    payload_null = TaskCreate(
        title="Reunión",
        scheduled_at=datetime.fromisoformat("2026-06-22T14:00:00+00:00"),
        duration_min=None,
    )
    payload_30 = TaskCreate(
        title="Reunión",
        scheduled_at=datetime.fromisoformat("2026-06-22T14:00:00+00:00"),
        duration_min=30,
    )

    result_null = await store.create_task(payload_null)
    result_30 = await store.create_task(payload_30)

    assert result_null["id"] != result_30["id"]
    assert result_null["duration_min"] is None
    assert result_30["duration_min"] == 30
