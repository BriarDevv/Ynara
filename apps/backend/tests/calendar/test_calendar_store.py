"""Tests de integración de ``CalendarEventStore`` (Fase E, ADR-021).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
siembra de ``test_events.py`` (flush sin commit; el savepoint del fixture limpia).

Cubren:
- ``create_event`` escribe el evento del user correcto (aislamiento por user_id).
- ``create_event`` devuelve un dict serializable sin metadata interna (no user_id).
- ``create_event`` es IDEMPOTENTE: re-crear el mismo evento NO inserta otra fila.
- Dos eventos legítimamente distintos sí crean dos filas.
- ``list_events`` filtra por ventana + user_id, ordena por start_at ASC.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar.store import CalendarEventStore
from app.enums import EventStatus
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.schemas.calendar_event import EventCreate

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


async def _count_events(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id == user_id)
        )
    ) or 0


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


async def test_create_event_writes_for_correct_user(db_session: AsyncSession) -> None:
    """``create_event`` persiste el evento atado al user_id del store."""
    user = await _seed_user(db_session)
    store = CalendarEventStore(db_session, user.id)

    result = await store.create_event(
        EventCreate(
            title="Reunión",
            start_at=_dt("2026-06-22T14:00:00+00:00"),
            duration_min=45,
            location="Oficina",
        )
    )

    # Dict serializable, sin metadata interna (mismo contrato que CalendarEventOut).
    assert result["title"] == "Reunión"
    assert result["duration_min"] == 45
    assert result["status"] == EventStatus.CONFIRMED.value
    assert "user_id" not in result

    # Persistido para el user correcto.
    persisted = await db_session.get(CalendarEvent, result["id"])
    assert persisted is not None
    assert persisted.user_id == user.id
    assert persisted.status == EventStatus.CONFIRMED


async def test_create_event_isolated_by_user(db_session: AsyncSession) -> None:
    """El evento de A no aparece para B; cada store solo escribe su user."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    store_a = CalendarEventStore(db_session, user_a.id)
    await store_a.create_event(
        EventCreate(title="De A", start_at=_dt("2026-06-22T09:00:00+00:00"), duration_min=30)
    )

    assert await _count_events(db_session, user_a.id) == 1
    assert await _count_events(db_session, user_b.id) == 0


async def test_create_event_is_idempotent(db_session: AsyncSession) -> None:
    """Re-crear el MISMO evento (tupla natural) NO inserta otra fila (idempotencia).

    Esta es la garantía que vuelve segura la pasada async del agente ante un retry de
    Celery: el mismo turno -> el mismo create_event -> no se agenda dos veces.
    """
    user = await _seed_user(db_session)
    store = CalendarEventStore(db_session, user.id)

    payload = EventCreate(
        title="Dentista",
        start_at=_dt("2026-06-23T10:00:00+00:00"),
        duration_min=60,
    )

    first = await store.create_event(payload)
    second = await store.create_event(payload)

    # Mismo id devuelto (la 2da no insertó: devolvió el existente).
    assert first["id"] == second["id"]
    # Una sola fila en la DB.
    assert await _count_events(db_session, user.id) == 1


async def test_create_event_distinct_events_create_two_rows(db_session: AsyncSession) -> None:
    """Dos eventos con tupla natural distinta crean dos filas (no colapsan)."""
    user = await _seed_user(db_session)
    store = CalendarEventStore(db_session, user.id)

    await store.create_event(
        EventCreate(title="A", start_at=_dt("2026-06-22T09:00:00+00:00"), duration_min=30)
    )
    await store.create_event(
        EventCreate(title="B", start_at=_dt("2026-06-22T11:00:00+00:00"), duration_min=30)
    )

    assert await _count_events(db_session, user.id) == 2


async def test_idempotency_does_not_collapse_across_users(db_session: AsyncSession) -> None:
    """Dos usuarios con el MISMO evento NO colapsan (el dedupe filtra por user_id)."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    payload = EventCreate(
        title="Standup", start_at=_dt("2026-06-22T09:00:00+00:00"), duration_min=15
    )
    await CalendarEventStore(db_session, user_a.id).create_event(payload)
    await CalendarEventStore(db_session, user_b.id).create_event(payload)

    assert await _count_events(db_session, user_a.id) == 1
    assert await _count_events(db_session, user_b.id) == 1


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


async def test_list_events_filters_window_and_orders_asc(db_session: AsyncSession) -> None:
    """``list_events`` trae solo los del user en la ventana, ordenados por start_at ASC."""
    user = await _seed_user(db_session)
    store = CalendarEventStore(db_session, user.id)

    await store.create_event(
        EventCreate(title="Tarde", start_at=_dt("2026-06-22T18:00:00+00:00"), duration_min=30)
    )
    await store.create_event(
        EventCreate(title="Temprano", start_at=_dt("2026-06-22T08:00:00+00:00"), duration_min=30)
    )
    # Fuera de la ventana (día siguiente): no debe aparecer.
    await store.create_event(
        EventCreate(title="Otro día", start_at=_dt("2026-06-23T08:00:00+00:00"), duration_min=30)
    )

    events = await store.list_events(
        _dt("2026-06-22T00:00:00+00:00"), _dt("2026-06-23T00:00:00+00:00")
    )

    titles = [e["title"] for e in events]
    assert titles == ["Temprano", "Tarde"]


async def test_list_events_isolated_by_user(db_session: AsyncSession) -> None:
    """``list_events`` del user A no devuelve eventos de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    await CalendarEventStore(db_session, user_b.id).create_event(
        EventCreate(title="De B", start_at=_dt("2026-06-22T10:00:00+00:00"), duration_min=30)
    )

    events = await CalendarEventStore(db_session, user_a.id).list_events(
        _dt("2026-06-22T00:00:00+00:00"), _dt("2026-06-23T00:00:00+00:00")
    )
    assert events == []
