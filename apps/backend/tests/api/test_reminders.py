"""Tests E2E del CRUD de ``/v1/reminders`` (PR-C).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
``test_events.py``: ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` + override de
``get_db``.

Cubre:
1. GET /reminders del user A → solo SUS recordatorios, total correcto, remind_at ASC.
2. POST /reminders → 201 con el ReminderOut (status pending server-set, sin user_id).
3. PATCH /reminders/{id} parcial → cambia solo lo enviado (incl. status).
4. DELETE /reminders/{id} → 204.
5. AISLAMIENTO: patch/delete de un recordatorio ajeno → 404 (sin oráculo) == inexistente.
6. sin token → 401.
7. rate-limit → 429 + Retry-After.
8. body inválido (text vacío / status fuera del enum / extra) → 422.
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
from app.enums import ReminderStatus
from app.main import app
from app.models.reminder import Reminder
from app.models.user import User

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_reminder(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    text: str = "Recordatorio",
    remind_at: str = "2026-06-22T09:00:00+00:00",
    status: ReminderStatus = ReminderStatus.PENDING,
) -> Reminder:
    reminder = Reminder(
        user_id=user_id,
        text=text,
        remind_at=datetime.fromisoformat(remind_at),
        status=status,
    )
    session.add(reminder)
    await session.flush()
    await session.refresh(reminder)
    return reminder


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# 1. GET /reminders del user A → solo SUS, total correcto, remind_at ASC
# ---------------------------------------------------------------------------


async def test_list_reminders_only_own_ordered(db_session: AsyncSession) -> None:
    """Lista solo los de A, ``total`` == 2, ordenados por remind_at ASC."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    late = await _seed_reminder(
        db_session, user_id=user_a.id, text="Tarde", remind_at="2026-06-22T18:00:00+00:00"
    )
    early = await _seed_reminder(
        db_session, user_id=user_a.id, text="Temprano", remind_at="2026-06-22T08:00:00+00:00"
    )
    b = await _seed_reminder(db_session, user_id=user_b.id, text="De B")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/reminders", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total"}
        assert body["total"] == 2
        ids = [it["id"] for it in body["items"]]
        assert str(b.id) not in ids
        assert ids == [str(early.id), str(late.id)]
        # ReminderOut NO expone user_id / timestamps.
        assert set(body["items"][0].keys()) == {"id", "text", "remind_at", "status"}
    finally:
        app.dependency_overrides.clear()


async def test_list_reminders_empty(db_session: AsyncSession) -> None:
    """Un user sin recordatorios → 200 con ``{items: [], total: 0}``."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/reminders", headers=_bearer(user.id))
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1"])
async def test_list_reminders_pagination_out_of_range_422(
    db_session: AsyncSession, query: str
) -> None:
    """``limit`` fuera de ``[1, 200]`` u ``offset`` negativo → 422."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/reminders?{query}", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. POST /reminders → 201, status pending server-set
# ---------------------------------------------------------------------------


async def test_create_reminder_returns_out_pending(db_session: AsyncSession) -> None:
    """201 con el recordatorio creado; status arranca pending; user_id no se filtra."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/reminders",
                headers=_bearer(user.id),
                json={"text": "Comprar pan", "remind_at": "2026-06-22T18:00:00+00:00"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["text"] == "Comprar pan"
        # status server-set (no viene del body).
        assert body["status"] == ReminderStatus.PENDING.value
        assert "user_id" not in body
        assert str(user.id) not in resp.text

        persisted = await db_session.get(Reminder, uuid.UUID(body["id"]))
        assert persisted is not None
        assert persisted.user_id == user.id
        assert persisted.status == ReminderStatus.PENDING
    finally:
        app.dependency_overrides.clear()


async def test_create_reminder_rejects_status_in_body(db_session: AsyncSession) -> None:
    """``status`` NO es seteable desde el body del create (extra=forbid) → 422."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/reminders",
                headers=_bearer(user.id),
                json={
                    "text": "x",
                    "remind_at": "2026-06-22T18:00:00+00:00",
                    "status": "sent",
                },
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. PATCH /reminders/{id} parcial (incl. status)
# ---------------------------------------------------------------------------


async def test_patch_reminder_partial(db_session: AsyncSession) -> None:
    """PATCH cambia solo lo enviado (status); el resto queda intacto."""
    user = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=user.id, text="Original")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/reminders/{rem.id}",
                headers=_bearer(user.id),
                json={"status": "cancelled"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == ReminderStatus.CANCELLED.value
        assert body["text"] == "Original"  # intacto

        await db_session.refresh(rem)
        assert rem.status == ReminderStatus.CANCELLED
    finally:
        app.dependency_overrides.clear()


async def test_patch_reminder_rejects_sent_status(db_session: AsyncSession) -> None:
    """PATCH ``{"status":"sent"}`` → 422: ``sent`` es server-only (anti double-dispatch)."""
    user = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=user.id, status=ReminderStatus.SENT)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/reminders/{rem.id}",
                headers=_bearer(user.id),
                json={"status": "sent"},
            )

        assert resp.status_code == 422
        # No re-tomó el recordatorio (sigue como estaba).
        await db_session.refresh(rem)
        assert rem.status == ReminderStatus.SENT
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("new_status", ["pending", "cancelled"])
async def test_patch_reminder_allows_pending_and_cancelled(
    db_session: AsyncSession, new_status: str
) -> None:
    """PATCH a ``pending`` (re-activar) o ``cancelled`` → 200 (los dos status seteables)."""
    user = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=user.id, status=ReminderStatus.SENT)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/reminders/{rem.id}",
                headers=_bearer(user.id),
                json={"status": new_status},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == new_status
    finally:
        app.dependency_overrides.clear()


async def test_create_reminder_text_over_max_length_422(db_session: AsyncSession) -> None:
    """POST con ``text`` > 1000 chars → 422 (cota del REST, MED-01)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post(
                "/v1/reminders",
                headers=_bearer(user.id),
                json={"text": "x" * 1001, "remind_at": "2026-06-22T18:00:00+00:00"},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. DELETE /reminders/{id} → 204
# ---------------------------------------------------------------------------


async def test_delete_reminder_204(db_session: AsyncSession) -> None:
    """DELETE de un recordatorio propio → 204; la fila se borra."""
    user = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/reminders/{rem.id}", headers=_bearer(user.id))

        assert resp.status_code == 204
        assert resp.content == b""
        gone = await db_session.get(Reminder, rem.id)
        assert gone is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. AISLAMIENTO: patch/delete ajeno → 404 sin oráculo == inexistente
# ---------------------------------------------------------------------------


async def test_patch_other_users_reminder_404(db_session: AsyncSession) -> None:
    """PATCH de un recordatorio de otro user → 404, sin mutar la fila del owner."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=owner.id, text="Del owner")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/reminders/{rem.id}",
                headers=_bearer(intruder.id),
                json={"status": "cancelled"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "recordatorio no encontrado"
        await db_session.refresh(rem)
        assert rem.status == ReminderStatus.PENDING
        assert str(owner.id) not in resp.text
    finally:
        app.dependency_overrides.clear()


async def test_delete_nonexistent_reminder_same_404(db_session: AsyncSession) -> None:
    """DELETE de un UUID inexistente → MISMO 404 que el ajeno."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.delete(f"/v1/reminders/{nonexistent}", headers=_bearer(user.id))
        assert resp.status_code == 404
        assert resp.json()["detail"] == "recordatorio no encontrado"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. sin token → 401
# ---------------------------------------------------------------------------


async def test_reminders_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en list / create / patch / delete."""
    user = await _seed_user(db_session)
    rem = await _seed_reminder(db_session, user_id=user.id)

    client = await _client(db_session)
    try:
        async with client:
            r_list = await client.get("/v1/reminders")
            r_create = await client.post(
                "/v1/reminders", json={"text": "x", "remind_at": "2026-06-22T09:00:00+00:00"}
            )
            r_patch = await client.patch(f"/v1/reminders/{rem.id}", json={"status": "sent"})
            r_delete = await client.delete(f"/v1/reminders/{rem.id}")
        assert r_list.status_code == 401
        assert r_create.status_code == 401
        assert r_patch.status_code == 401
        assert r_delete.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. rate-limit → 429
# ---------------------------------------------------------------------------


async def test_reminders_rate_limited_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cruzar el rate-limit (bucket de reminders) → 429 + ``Retry-After``."""
    user = await _seed_user(db_session)

    async def _deny(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr("app.api.v1.reminders.check_reminders_rate_limit", _deny)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/reminders", headers=_bearer(user.id))
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. body inválido → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_body",
    [
        {"text": "", "remind_at": "2026-06-22T09:00:00+00:00"},  # text vacío
        {"text": "x"},  # falta remind_at
        {"text": "x", "remind_at": "no-es-fecha"},  # remind_at no-ISO
    ],
)
async def test_create_reminder_invalid_body_422(
    db_session: AsyncSession, bad_body: dict[str, object]
) -> None:
    """text vacío / remind_at faltante o no-ISO → 422."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.post("/v1/reminders", headers=_bearer(user.id), json=bad_body)
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
