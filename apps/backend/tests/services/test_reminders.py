"""Tests de integración de ``ReminderStore`` (PR-C).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
siembra espejado de ``test_task_store.py`` / ``test_calendar_store.py``.

Cubren:
- ``create_reminder`` (tool) es IDEMPOTENTE: dedup por ``(user_id, text, remind_at)``.
- ``add_reminder`` (REST) NO deduplica: dos altas idénticas crean dos filas.
- ``list_all`` filtra por user y ordena por ``remind_at`` ASC + paginación.
- ``update_reminder`` / ``delete_reminder`` con aislamiento (None/False para ajeno).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ReminderStatus
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.reminder import ReminderCreate
from app.services.reminders import ReminderStore

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


async def _count(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id)
        )
    ) or 0


# ---------------------------------------------------------------------------
# create_reminder (tool) — idempotente
# ---------------------------------------------------------------------------


async def test_create_reminder_writes_pending(db_session: AsyncSession) -> None:
    """``create_reminder`` persiste el recordatorio ``pending`` del user correcto."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)

    result = await store.create_reminder(
        ReminderCreate(text="Llamar al dentista", remind_at=_dt("2026-06-22T14:00:00+00:00"))
    )

    assert result["text"] == "Llamar al dentista"
    assert result["status"] == ReminderStatus.PENDING.value
    assert "user_id" not in result

    persisted = await db_session.get(Reminder, UUID(str(result["id"])))
    assert persisted is not None
    assert persisted.user_id == user.id
    assert persisted.status == ReminderStatus.PENDING


async def test_create_reminder_is_idempotent(db_session: AsyncSession) -> None:
    """Re-crear el MISMO recordatorio (tupla natural) NO inserta otra fila."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    payload = ReminderCreate(text="Pagar luz", remind_at=_dt("2026-06-23T10:00:00+00:00"))

    first = await store.create_reminder(payload)
    second = await store.create_reminder(payload)

    assert first["id"] == second["id"]
    assert await _count(db_session, user.id) == 1


async def test_create_reminder_isolated_by_user(db_session: AsyncSession) -> None:
    """El mismo recordatorio en dos users NO colapsa (dedup filtra por user_id)."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    payload = ReminderCreate(text="Standup", remind_at=_dt("2026-06-22T09:00:00+00:00"))

    await ReminderStore(db_session, user_a.id).create_reminder(payload)
    await ReminderStore(db_session, user_b.id).create_reminder(payload)

    assert await _count(db_session, user_a.id) == 1
    assert await _count(db_session, user_b.id) == 1


# ---------------------------------------------------------------------------
# add_reminder (REST) — NO dedup
# ---------------------------------------------------------------------------


async def test_add_reminder_no_dedup(db_session: AsyncSession) -> None:
    """``add_reminder`` (POST REST) INSERTA siempre, aunque sea idéntico."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    payload = ReminderCreate(text="Idéntico", remind_at=_dt("2026-06-22T12:00:00+00:00"))

    first = await store.add_reminder(payload)
    second = await store.add_reminder(payload)

    assert first["id"] != second["id"]
    assert await _count(db_session, user.id) == 2


# ---------------------------------------------------------------------------
# list_all — orden ASC + paginación + aislamiento
# ---------------------------------------------------------------------------


async def test_list_all_orders_remind_at_asc(db_session: AsyncSession) -> None:
    """``list_all`` ordena por ``remind_at`` ASC (el más próximo primero)."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    await store.add_reminder(
        ReminderCreate(text="Tarde", remind_at=_dt("2026-06-22T18:00:00+00:00"))
    )
    await store.add_reminder(
        ReminderCreate(text="Temprano", remind_at=_dt("2026-06-22T08:00:00+00:00"))
    )

    rows = await store.list_all(limit=100, offset=0)
    assert [r["text"] for r in rows] == ["Temprano", "Tarde"]


async def test_list_all_paginates(db_session: AsyncSession) -> None:
    """``limit``/``offset`` pagina con el mismo orden estable, sin solapar."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    for hour in (8, 10, 12):
        await store.add_reminder(
            ReminderCreate(text=f"R{hour}", remind_at=_dt(f"2026-06-22T{hour:02d}:00:00+00:00"))
        )

    page1 = await store.list_all(limit=2, offset=0)
    page2 = await store.list_all(limit=2, offset=2)

    assert [r["text"] for r in page1] == ["R8", "R10"]
    assert [r["text"] for r in page2] == ["R12"]


async def test_list_all_isolated_by_user(db_session: AsyncSession) -> None:
    """``list_all`` del user A no devuelve recordatorios de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await ReminderStore(db_session, user_b.id).add_reminder(
        ReminderCreate(text="De B", remind_at=_dt("2026-06-22T09:00:00+00:00"))
    )

    assert await ReminderStore(db_session, user_a.id).list_all(limit=100, offset=0) == []


# ---------------------------------------------------------------------------
# list_window (tool) — ventana de tiempo
# ---------------------------------------------------------------------------


async def test_list_window_filters_by_range(db_session: AsyncSession) -> None:
    """``list_window`` devuelve solo los que vencen en ``[from_dt, to_dt)``."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    await store.add_reminder(
        ReminderCreate(text="Dentro", remind_at=_dt("2026-06-22T10:00:00+00:00"))
    )
    await store.add_reminder(
        ReminderCreate(text="Fuera", remind_at=_dt("2026-06-25T10:00:00+00:00"))
    )

    rows = await store.list_window(
        _dt("2026-06-22T00:00:00+00:00"), _dt("2026-06-23T00:00:00+00:00")
    )
    assert [r["text"] for r in rows] == ["Dentro"]


async def test_list_window_only_pending(db_session: AsyncSession) -> None:
    """``list_window`` (tool del agente) solo ve PENDING; sent/cancelled quedan fuera (MED-cr-2)."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    # Tres recordatorios en la misma ventana, distinto status.
    pend = Reminder(
        user_id=user.id,
        text="Pendiente",
        remind_at=_dt("2026-06-22T10:00:00+00:00"),
        status=ReminderStatus.PENDING,
    )
    sent = Reminder(
        user_id=user.id,
        text="Enviado",
        remind_at=_dt("2026-06-22T11:00:00+00:00"),
        status=ReminderStatus.SENT,
    )
    cancelled = Reminder(
        user_id=user.id,
        text="Cancelado",
        remind_at=_dt("2026-06-22T12:00:00+00:00"),
        status=ReminderStatus.CANCELLED,
    )
    db_session.add_all([pend, sent, cancelled])
    await db_session.flush()

    rows = await store.list_window(
        _dt("2026-06-22T00:00:00+00:00"), _dt("2026-06-23T00:00:00+00:00")
    )
    assert [r["text"] for r in rows] == ["Pendiente"]


# ---------------------------------------------------------------------------
# update_reminder / delete_reminder — aislamiento
# ---------------------------------------------------------------------------


async def test_update_reminder_partial(db_session: AsyncSession) -> None:
    """``update_reminder`` aplica solo los campos enviados; devuelve el dict actualizado."""
    user = await _seed_user(db_session)
    store = ReminderStore(db_session, user.id)
    created = await store.add_reminder(
        ReminderCreate(text="Original", remind_at=_dt("2026-06-22T10:00:00+00:00"))
    )

    updated = await store.update_reminder(
        UUID(str(created["id"])), {"status": ReminderStatus.CANCELLED}
    )
    assert updated is not None
    assert updated["status"] == ReminderStatus.CANCELLED.value
    assert updated["text"] == "Original"  # intacto


async def test_update_reminder_other_user_returns_none(db_session: AsyncSession) -> None:
    """``update_reminder`` de un recordatorio ajeno → None (aislamiento)."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    created = await ReminderStore(db_session, owner.id).add_reminder(
        ReminderCreate(text="Del owner", remind_at=_dt("2026-06-22T10:00:00+00:00"))
    )

    result = await ReminderStore(db_session, intruder.id).update_reminder(
        UUID(str(created["id"])), {"status": ReminderStatus.CANCELLED}
    )
    assert result is None


async def test_delete_reminder_owned_and_isolation(db_session: AsyncSession) -> None:
    """``delete_reminder`` borra el propio (True); ajeno/inexistente → False."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    created = await ReminderStore(db_session, owner.id).add_reminder(
        ReminderCreate(text="Borrable", remind_at=_dt("2026-06-22T10:00:00+00:00"))
    )

    # Ajeno → False, sin borrar.
    assert (
        await ReminderStore(db_session, intruder.id).delete_reminder(UUID(str(created["id"])))
        is False
    )
    assert await _count(db_session, owner.id) == 1

    # Inexistente → False.
    assert await ReminderStore(db_session, owner.id).delete_reminder(uuid4()) is False

    # Propio → True, se borra.
    assert (
        await ReminderStore(db_session, owner.id).delete_reminder(UUID(str(created["id"]))) is True
    )
    assert await _count(db_session, owner.id) == 0
