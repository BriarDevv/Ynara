"""Tests E2E del CRUD de ``/v1/events`` (dominio Agenda, ADR-018).

Todos son ``integration`` (tocan la DB de tests dedicada vía ``db_session``). El
patrón es el de ``test_sessions.py`` / ``test_sessions_close.py``:

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, así el
  endpoint lee/escribe la MISMA sesión donde el test sembró.

El CRUD NO toca LLM ni Redis, así que NO se overridean los clientes Fake (a
diferencia de ``/chat``): solo se necesita el override de ``get_db``. El fixture
``db_session`` usa el patrón savepoint: un ``commit()`` del endpoint commitea el
SAVEPOINT y el rollback de la transacción externa lo descarta al final, sin
limpieza manual por test.

Cubre el spec (aislamiento es el test CLAVE):
1. ``GET /events`` del user A → solo SUS eventos, ``total`` correcto, ordenados ASC.
2. ``POST /events`` → 201 con el ``CalendarEventOut`` (sin user_id/timestamps).
3. ``PATCH /events/{id}`` parcial → solo cambia lo enviado.
4. ``PATCH`` recurrence sin time_zone (estado mergeado) → 422.
5. ``DELETE /events/{id}`` → 204.
6. AISLAMIENTO: get/patch/delete de un evento ajeno → 404 (sin oráculo) == inexistente.
7. sin token → 401.
8. Invariante recurrence en el create → 422.
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
from app.enums import EventStatus, Mode
from app.main import app
from app.models.calendar_event import CalendarEvent
from app.models.user import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers de siembra (flush, NO commit — el savepoint del fixture limpia)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str = "Evento",
    start_at: str = "2026-06-22T09:00:00+00:00",
    duration_min: int = 60,
    mode: Mode | None = None,
    status: EventStatus = EventStatus.CONFIRMED,
    location: str | None = None,
    time_zone: str | None = None,
    all_day: bool = False,
    recurrence: list[str] | None = None,
) -> CalendarEvent:
    """Inserta un CalendarEvent para ``user_id`` y hace flush (sin commit)."""
    from datetime import datetime

    event = CalendarEvent(
        user_id=user_id,
        title=title,
        start_at=datetime.fromisoformat(start_at),
        duration_min=duration_min,
        mode=mode,
        status=status,
        location=location,
        time_zone=time_zone,
        all_day=all_day,
        recurrence=recurrence,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


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
# 1. GET /events del user A → solo SUS eventos, total correcto, ordenados ASC
# ---------------------------------------------------------------------------


async def test_list_events_only_own_ordered(db_session: AsyncSession) -> None:
    """Lista solo los eventos de A, ``total`` == 2, ordenados por start_at ASC."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    # Insertados fuera de orden cronológico para verificar el ORDER BY ASC.
    ev_late = await _seed_event(
        db_session, user_id=user_a.id, title="Tarde", start_at="2026-06-22T18:00:00+00:00"
    )
    ev_early = await _seed_event(
        db_session, user_id=user_a.id, title="Temprano", start_at="2026-06-22T08:00:00+00:00"
    )
    # 1 evento de B: NO debe aparecer en el listado de A.
    ev_b = await _seed_event(db_session, user_id=user_b.id, title="De B")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/events", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total"}

        # total = conteo del user A (2), no cuenta el de B.
        assert body["total"] == 2
        ids = [it["id"] for it in body["items"]]
        assert len(ids) == 2
        assert str(ev_b.id) not in ids  # aislamiento: nada de B.

        # Orden start_at ASC: el más temprano primero.
        assert ids == [str(ev_early.id), str(ev_late.id)]

        # CalendarEventOut NO expone user_id / created_at / updated_at.
        item = body["items"][0]
        assert set(item.keys()) == {
            "id",
            "title",
            "start_at",
            "duration_min",
            "mode",
            "status",
            "location",
            "time_zone",
            "all_day",
            "recurrence",
        }
    finally:
        app.dependency_overrides.clear()


async def test_list_events_empty(db_session: AsyncSession) -> None:
    """Un user sin eventos → 200 con ``{items: [], total: 0}`` (``total or 0``)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/events", headers=_bearer(user.id))

        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. POST /events → 201 con el CalendarEventOut
# ---------------------------------------------------------------------------


async def test_create_event_returns_out(db_session: AsyncSession) -> None:
    """201 con el evento creado; status arranca confirmed; user_id no se filtra."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/events",
                headers=_bearer(user.id),
                json={
                    "title": "Reunión",
                    "start_at": "2026-06-22T14:00:00+00:00",
                    "duration_min": 45,
                    "mode": "productividad",
                    "location": "Oficina",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Reunión"
        assert body["duration_min"] == 45
        assert body["mode"] == Mode.PRODUCTIVIDAD.value
        assert body["location"] == "Oficina"
        # status arranca confirmed (no viene del body).
        assert body["status"] == EventStatus.CONFIRMED.value
        # defaults de los campos opcionales.
        assert body["all_day"] is False
        assert body["time_zone"] is None
        assert body["recurrence"] is None
        # user_id NO se expone en la respuesta.
        assert "user_id" not in body
        assert str(user.id) not in resp.text

        # Persistido en la DB.
        persisted = await db_session.get(CalendarEvent, uuid.UUID(body["id"]))
        assert persisted is not None
        assert persisted.user_id == user.id
        assert persisted.status == EventStatus.CONFIRMED
    finally:
        app.dependency_overrides.clear()


async def test_create_event_minimal(db_session: AsyncSession) -> None:
    """Form mínimo (title + start_at + duration_min): mode/location defaultean a null."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/events",
                headers=_bearer(user.id),
                json={
                    "title": "Mínimo",
                    "start_at": "2026-06-22T10:00:00+00:00",
                    "duration_min": 30,
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["mode"] is None
        assert body["location"] is None
        assert body["status"] == EventStatus.CONFIRMED.value
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. PATCH /events/{id} parcial → solo cambia lo enviado
# ---------------------------------------------------------------------------


async def test_patch_event_partial(db_session: AsyncSession) -> None:
    """PATCH solo toca los campos enviados; los demás quedan intactos."""
    user = await _seed_user(db_session)
    ev = await _seed_event(
        db_session,
        user_id=user.id,
        title="Original",
        duration_min=60,
        location="Casa",
        status=EventStatus.CONFIRMED,
    )

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={"title": "Editado", "status": "tentative"},
            )

        assert resp.status_code == 200
        body = resp.json()
        # Cambiados.
        assert body["title"] == "Editado"
        assert body["status"] == EventStatus.TENTATIVE.value
        # Intactos (no enviados).
        assert body["duration_min"] == 60
        assert body["location"] == "Casa"

        # Persistido.
        await db_session.refresh(ev)
        assert ev.title == "Editado"
        assert ev.status == EventStatus.TENTATIVE
        assert ev.location == "Casa"
    finally:
        app.dependency_overrides.clear()


async def test_patch_event_clears_location_with_null(db_session: AsyncSession) -> None:
    """Un PATCH puede pisar location con null (campo nullable enviado explícito)."""
    user = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=user.id, location="Casa")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={"location": None},
            )

        assert resp.status_code == 200
        assert resp.json()["location"] is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. PATCH recurrence sin time_zone (estado mergeado) → 422
# ---------------------------------------------------------------------------


async def test_patch_recurrence_without_time_zone_422(db_session: AsyncSession) -> None:
    """Agregar recurrence a un evento sin time_zone (ni en el patch) → 422 (ADR-018)."""
    user = await _seed_user(db_session)
    # Evento sin recurrence ni time_zone.
    ev = await _seed_event(db_session, user_id=user.id, time_zone=None, recurrence=None)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={"recurrence": ["RRULE:FREQ=WEEKLY"]},
            )

        assert resp.status_code == 422

        # No se commiteó el cambio: la fila sigue sin recurrence.
        await db_session.refresh(ev)
        assert ev.recurrence is None
    finally:
        app.dependency_overrides.clear()


async def test_patch_recurrence_with_time_zone_in_patch_ok(db_session: AsyncSession) -> None:
    """Agregar recurrence + time_zone en el MISMO patch → 200 (invariante satisfecha)."""
    user = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=user.id, time_zone=None, recurrence=None)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={
                    "recurrence": ["RRULE:FREQ=WEEKLY"],
                    "time_zone": "America/Argentina/Buenos_Aires",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["recurrence"] == ["RRULE:FREQ=WEEKLY"]
        assert body["time_zone"] == "America/Argentina/Buenos_Aires"
    finally:
        app.dependency_overrides.clear()


async def test_patch_recurrence_with_stored_time_zone_ok(db_session: AsyncSession) -> None:
    """Agregar recurrence apoyándose en el time_zone YA guardado → 200 (estado mergeado)."""
    user = await _seed_user(db_session)
    # Evento que ya tiene time_zone guardado, sin recurrence.
    ev = await _seed_event(
        db_session, user_id=user.id, time_zone="America/Argentina/Buenos_Aires", recurrence=None
    )

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={"recurrence": ["RRULE:FREQ=DAILY"]},
            )

        assert resp.status_code == 200
        assert resp.json()["recurrence"] == ["RRULE:FREQ=DAILY"]
    finally:
        app.dependency_overrides.clear()


async def test_patch_clear_time_zone_with_stored_recurrence_422(db_session: AsyncSession) -> None:
    """Pisar ``time_zone`` con null en un evento con recurrence guardada → 422.

    El camino más realista de la invariante sobre el estado MERGEADO: el evento ya
    tiene recurrence + time_zone, y el patch borra el time_zone (el usuario destilda
    el huso) → el evento resultante queda con recurrence sin huso → 422, sin commit.
    """
    user = await _seed_user(db_session)
    ev = await _seed_event(
        db_session,
        user_id=user.id,
        recurrence=["RRULE:FREQ=WEEKLY"],
        time_zone="America/Argentina/Buenos_Aires",
    )

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(user.id),
                json={"time_zone": None},
            )

        assert resp.status_code == 422
        # No se commiteó: la fila conserva el time_zone original.
        await db_session.refresh(ev)
        assert ev.time_zone == "America/Argentina/Buenos_Aires"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. DELETE /events/{id} → 204
# ---------------------------------------------------------------------------


async def test_delete_event_204(db_session: AsyncSession) -> None:
    """DELETE de un evento propio → 204; la fila se borra de la DB."""
    user = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/events/{ev.id}", headers=_bearer(user.id))

        assert resp.status_code == 204
        assert resp.content == b""

        # Borrado de la DB.
        gone = await db_session.get(CalendarEvent, ev.id)
        assert gone is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. AISLAMIENTO: patch/delete de evento ajeno → 404 (sin oráculo) == inexistente
# ---------------------------------------------------------------------------


async def test_patch_other_users_event_404_no_oracle(db_session: AsyncSession) -> None:
    """PATCH de un evento de otro user → 404, sin mutar la fila del owner."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=owner.id, title="Del owner")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{ev.id}",
                headers=_bearer(intruder.id),
                json={"title": "Hackeado"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "evento no encontrado"
        # No se mutó el evento del owner.
        await db_session.refresh(ev)
        assert ev.title == "Del owner"
        # El user_id del owner no se filtra.
        assert str(owner.id) not in resp.text
    finally:
        app.dependency_overrides.clear()


async def test_delete_other_users_event_404_no_oracle(db_session: AsyncSession) -> None:
    """DELETE de un evento de otro user → 404, sin borrar la fila del owner."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=owner.id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/events/{ev.id}", headers=_bearer(intruder.id))

        assert resp.status_code == 404
        assert resp.json()["detail"] == "evento no encontrado"
        # El evento del owner sigue existiendo.
        still = await db_session.get(CalendarEvent, ev.id)
        assert still is not None
    finally:
        app.dependency_overrides.clear()


async def test_patch_nonexistent_event_same_404(db_session: AsyncSession) -> None:
    """PATCH de un UUID inexistente → MISMO 404 (status + detail) que el ajeno."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/events/{nonexistent}",
                headers=_bearer(user.id),
                json={"title": "x"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "evento no encontrado"
    finally:
        app.dependency_overrides.clear()


async def test_delete_nonexistent_event_same_404(db_session: AsyncSession) -> None:
    """DELETE de un UUID inexistente → MISMO 404 (status + detail) que el ajeno."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/events/{nonexistent}", headers=_bearer(user.id))

        assert resp.status_code == 404
        assert resp.json()["detail"] == "evento no encontrado"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. sin token → 401 (todas las rutas)
# ---------------------------------------------------------------------------


async def test_events_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en list / create / patch / delete."""
    user = await _seed_user(db_session)
    ev = await _seed_event(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            r_list = await client.get("/v1/events")
            r_create = await client.post(
                "/v1/events",
                json={"title": "x", "start_at": "2026-06-22T09:00:00+00:00", "duration_min": 30},
            )
            r_patch = await client.patch(f"/v1/events/{ev.id}", json={"title": "x"})
            r_delete = await client.delete(f"/v1/events/{ev.id}")
        assert r_list.status_code == 401
        assert r_create.status_code == 401
        assert r_patch.status_code == 401
        assert r_delete.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. Invariante recurrence en el create → 422
# ---------------------------------------------------------------------------


async def test_create_recurrence_without_time_zone_422(db_session: AsyncSession) -> None:
    """POST con recurrence y sin time_zone → 422 (invariante ADR-018, schema)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/events",
                headers=_bearer(user.id),
                json={
                    "title": "Recurrente",
                    "start_at": "2026-06-22T09:00:00+00:00",
                    "duration_min": 30,
                    "recurrence": ["RRULE:FREQ=WEEKLY"],
                },
            )

        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_create_recurrence_with_time_zone_ok(db_session: AsyncSession) -> None:
    """POST con recurrence + time_zone → 201 (invariante satisfecha)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/events",
                headers=_bearer(user.id),
                json={
                    "title": "Recurrente",
                    "start_at": "2026-06-22T09:00:00+00:00",
                    "duration_min": 30,
                    "recurrence": ["RRULE:FREQ=WEEKLY"],
                    "time_zone": "America/Argentina/Buenos_Aires",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["recurrence"] == ["RRULE:FREQ=WEEKLY"]
        assert body["time_zone"] == "America/Argentina/Buenos_Aires"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Validación de body: title vacío / duration_min no positivo → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_body",
    [
        {"title": "", "start_at": "2026-06-22T09:00:00+00:00", "duration_min": 30},
        {"title": "x", "start_at": "2026-06-22T09:00:00+00:00", "duration_min": 0},
        {"title": "x", "start_at": "2026-06-22T09:00:00+00:00", "duration_min": -5},
        {"title": "x", "start_at": "no-es-fecha", "duration_min": 30},
    ],
)
async def test_create_event_invalid_body_422(
    db_session: AsyncSession, bad_body: dict[str, object]
) -> None:
    """title vacío / duration_min <= 0 / start_at no-ISO → 422 (mirror de Zod)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/events", headers=_bearer(user.id), json=bad_body)
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
