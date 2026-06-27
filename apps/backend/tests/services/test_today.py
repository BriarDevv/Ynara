"""Tests del ``tz`` en las derivaciones del dashboard **Hoy** (``app/services/today.py``).

Todos ``integration`` (``build_recap``/``build_suggestions`` consultan ``TaskStore`` →
tocan la DB de tests vía ``db_session``). Foco: el "hoy" del usuario se computa en SU
huso, no en UTC.

La cobertura de la lógica de derivación (highlights, cap, orden) vive en
``tests/api/test_today.py``; acá solo se cubre el parámetro ``tz`` nuevo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.services.today import build_recap, build_suggestions

pytestmark = pytest.mark.integration

_AR = "America/Argentina/Buenos_Aires"


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def test_build_recap_date_in_user_tz(db_session: AsyncSession) -> None:
    """``build_recap(tz=...)`` expresa ``date`` en el huso del usuario, no en UTC.

    Un instante 01:00 UTC del 22/06 cae el 21/06 22:00 en Argentina (UTC-03:00): el
    ``date`` del recap debe quedar en ESE día local (21/06) y con el offset -03:00, no
    el 22/06 de UTC.
    """
    user = await _seed_user(db_session)
    # Una tarea cerrada para que haya contenido (irrelevante para el assert de date).
    db_session.add(Task(user_id=user.id, title="Hecha", status=TaskStatus.DONE))
    await db_session.flush()

    now_utc = datetime(2026, 6, 22, 1, 0, tzinfo=UTC)
    recap = await build_recap(db_session, user.id, now=now_utc, tz=_AR)

    # Mismo instante absoluto, pero expresado en Argentina.
    assert recap.date == now_utc
    assert recap.date.utcoffset() == timedelta(hours=-3)
    # El "día" local es el 21 (un día antes que el 22 de UTC).
    assert recap.date.year == 2026
    assert recap.date.month == 6
    assert recap.date.day == 21


async def test_build_recap_default_tz_utc_unchanged(db_session: AsyncSession) -> None:
    """Sin ``tz`` (default UTC) el ``date`` es el instante UTC (back-compat)."""
    user = await _seed_user(db_session)
    now_utc = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)

    recap = await build_recap(db_session, user.id, now=now_utc)

    assert recap.date == now_utc
    assert recap.date.utcoffset() == timedelta(0)


async def test_build_suggestions_accepts_tz(db_session: AsyncSession) -> None:
    """``build_suggestions`` acepta ``tz`` y sigue filtrando por instante absoluto.

    La conversión de huso NO cambia el instante: una tarea a futuro respecto del ``now``
    absoluto sigue surfaceándose con o sin ``tz``.
    """
    user = await _seed_user(db_session)
    now_utc = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)
    future = (now_utc + timedelta(hours=2)).astimezone(ZoneInfo(_AR))
    db_session.add(
        Task(user_id=user.id, title="Reunión", status=TaskStatus.PENDING, scheduled_at=future)
    )
    await db_session.flush()

    out = await build_suggestions(db_session, user.id, now=now_utc, tz=_AR)

    assert len(out) == 1
    assert out[0].title == "Preparate para Reunión"
