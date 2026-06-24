"""Tests de integración de ``TaskStore`` (Fase D1).

Todos ``integration`` (tocan la DB de tests dedicada vía ``db_session``). Patrón de
siembra de ``test_task_store`` espejado de ``test_calendar_store.py`` (flush sin
commit; el savepoint del fixture limpia).

Cubren:
- ``create_task`` escribe la tarea del user correcto (aislamiento por user_id).
- ``create_task`` devuelve un dict serializable sin metadata interna (no user_id).
- ``create_task`` es IDEMPOTENTE: re-crear la misma tarea NO inserta otra fila.
- Idempotencia con ``scheduled_at`` NULL (dedupe por IS NULL).
- Dos tareas legítimamente distintas sí crean dos filas.
- ``list_tasks`` filtra por user_id y ordena pending primero + scheduled_at asc.
- ``set_status`` togglea el estado; 404 (None) sin oráculo para ajena/inexistente.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate
from app.services.tasks import TaskStore

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


async def _count_tasks(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(select(func.count()).select_from(Task).where(Task.user_id == user_id))
    ) or 0


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


async def test_create_task_writes_for_correct_user(db_session: AsyncSession) -> None:
    """``create_task`` persiste la tarea atada al user_id del store."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    result = await store.create_task(
        TaskCreate(
            title="Llamar al dentista",
            scheduled_at=_dt("2026-06-22T14:00:00+00:00"),
            duration_min=15,
        )
    )

    # Dict serializable, sin metadata interna (mismo contrato que TaskOut).
    assert result["title"] == "Llamar al dentista"
    assert result["duration_min"] == 15
    assert result["status"] == TaskStatus.PENDING.value
    assert "user_id" not in result

    # Persistida para el user correcto.
    persisted = await db_session.get(Task, result["id"])
    assert persisted is not None
    assert persisted.user_id == user.id
    assert persisted.status == TaskStatus.PENDING


async def test_create_task_minimal_no_schedule(db_session: AsyncSession) -> None:
    """Una tarea sin horario (scheduled_at/duration_min None) se persiste igual."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    result = await store.create_task(TaskCreate(title="Pendiente sin hora"))

    assert result["scheduled_at"] is None
    assert result["duration_min"] is None
    assert result["status"] == TaskStatus.PENDING.value


async def test_create_task_isolated_by_user(db_session: AsyncSession) -> None:
    """La tarea de A no aparece para B; cada store solo escribe su user."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    store_a = TaskStore(db_session, user_a.id)
    await store_a.create_task(TaskCreate(title="De A"))

    assert await _count_tasks(db_session, user_a.id) == 1
    assert await _count_tasks(db_session, user_b.id) == 0


async def test_create_task_is_idempotent(db_session: AsyncSession) -> None:
    """Re-crear la MISMA tarea (tupla natural) NO inserta otra fila (idempotencia).

    Garantía que vuelve segura la pasada async del agente ante un retry de Celery: el
    mismo turno -> el mismo create_task -> no se crea dos veces.
    """
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    payload = TaskCreate(
        title="Comprar pan",
        scheduled_at=_dt("2026-06-23T10:00:00+00:00"),
        duration_min=10,
    )

    first = await store.create_task(payload)
    second = await store.create_task(payload)

    assert first["id"] == second["id"]
    assert await _count_tasks(db_session, user.id) == 1


async def test_create_task_idempotent_with_null_schedule(db_session: AsyncSession) -> None:
    """Idempotencia también cuando ``scheduled_at`` es NULL (dedupe por IS NULL)."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    payload = TaskCreate(title="Pendiente sin hora")
    first = await store.create_task(payload)
    second = await store.create_task(payload)

    assert first["id"] == second["id"]
    assert await _count_tasks(db_session, user.id) == 1


async def test_create_task_distinct_tasks_create_two_rows(db_session: AsyncSession) -> None:
    """Dos tareas con tupla natural distinta crean dos filas (no colapsan)."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    await store.create_task(TaskCreate(title="A"))
    await store.create_task(TaskCreate(title="B"))

    assert await _count_tasks(db_session, user.id) == 2


async def test_idempotency_does_not_collapse_across_users(db_session: AsyncSession) -> None:
    """Dos usuarios con la MISMA tarea NO colapsan (el dedupe filtra por user_id)."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    payload = TaskCreate(title="Standup")
    await TaskStore(db_session, user_a.id).create_task(payload)
    await TaskStore(db_session, user_b.id).create_task(payload)

    assert await _count_tasks(db_session, user_a.id) == 1
    assert await _count_tasks(db_session, user_b.id) == 1


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


async def test_list_tasks_pending_first_then_scheduled_asc(db_session: AsyncSession) -> None:
    """``list_tasks``: pending arriba, luego por scheduled_at ASC (None al final)."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    # Una done (debe ir al final pese a tener horario temprano).
    done = await store.create_task(
        TaskCreate(title="Hecha", scheduled_at=_dt("2026-06-22T06:00:00+00:00"))
    )
    await store.set_status(UUID(str(done["id"])), TaskStatus.DONE)
    # Pending con horario tarde.
    await store.create_task(
        TaskCreate(title="Tarde", scheduled_at=_dt("2026-06-22T18:00:00+00:00"))
    )
    # Pending con horario temprano.
    await store.create_task(
        TaskCreate(title="Temprano", scheduled_at=_dt("2026-06-22T08:00:00+00:00"))
    )
    # Pending sin horario (va al final del grupo pending).
    await store.create_task(TaskCreate(title="Sin hora"))

    tasks = await store.list_tasks()
    titles = [t["title"] for t in tasks]

    # pending primero (Temprano, Tarde por scheduled asc; Sin hora al final del grupo
    # pending por nulls_last); done último.
    assert titles == ["Temprano", "Tarde", "Sin hora", "Hecha"]


async def test_list_tasks_isolated_by_user(db_session: AsyncSession) -> None:
    """``list_tasks`` del user A no devuelve tareas de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)

    await TaskStore(db_session, user_b.id).create_task(TaskCreate(title="De B"))

    tasks = await TaskStore(db_session, user_a.id).list_tasks()
    assert tasks == []


# ---------------------------------------------------------------------------
# set_status
# ---------------------------------------------------------------------------


async def test_set_status_toggles(db_session: AsyncSession) -> None:
    """``set_status`` cambia el estado y devuelve el dict serializable actualizado."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)
    created = await store.create_task(TaskCreate(title="Toggle"))
    assert created["status"] == TaskStatus.PENDING.value

    updated = await store.set_status(UUID(str(created["id"])), TaskStatus.DONE)
    assert updated is not None
    assert updated["status"] == TaskStatus.DONE.value
    assert updated["id"] == created["id"]

    # Persistido.
    persisted = await db_session.get(Task, created["id"])
    assert persisted is not None
    assert persisted.status == TaskStatus.DONE


async def test_set_status_nonexistent_returns_none(db_session: AsyncSession) -> None:
    """Setear status de una tarea inexistente -> None (el caller traduce a 404)."""
    user = await _seed_user(db_session)
    store = TaskStore(db_session, user.id)

    result = await store.set_status(uuid4(), TaskStatus.DONE)
    assert result is None


async def test_set_status_other_users_task_returns_none(db_session: AsyncSession) -> None:
    """Setear status de una tarea ajena -> None (aislamiento, sin oráculo)."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    created = await TaskStore(db_session, owner.id).create_task(TaskCreate(title="Del owner"))

    # El store del intruso no la encuentra.
    result = await TaskStore(db_session, intruder.id).set_status(
        UUID(str(created["id"])), TaskStatus.DONE
    )
    assert result is None

    # La tarea del owner NO se mutó.
    persisted = await db_session.get(Task, created["id"])
    assert persisted is not None
    assert persisted.status == TaskStatus.PENDING
