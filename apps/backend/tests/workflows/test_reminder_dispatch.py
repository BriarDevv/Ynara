"""Tests del worker de despacho de recordatorios (``dispatch_due_reminders``, PR-C).

Dos niveles:

- **Unit (sin DB)**: el task wrapper corre el cuerpo async y es fail-open (un fallo NO
  tumba el worker; se loguea sin datos de usuario). Mismo patrón que
  ``tests/workflows/test_episodic_retention.py``.
- **Integración** (``integration``): siembra recordatorios vencidos/futuros + device
  tokens y, con ``now`` inyectado y un notifier fake, verifica que despacha SOLO los
  vencidos (``remind_at <= now``), los marca ``sent``, deja los futuros intactos y devuelve
  el conteo. Cubre el borde ``<=`` (el exacto en ``now`` se despacha).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DevicePlatform, ReminderStatus
from app.models.device_token import DeviceToken
from app.models.reminder import Reminder
from app.models.user import User
from app.workflows.reminder_dispatch import (
    _async_dispatch_due_reminders,
    dispatch_due_reminders,
)

# ---------------------------------------------------------------------------
# Unit: el task wrapper es fail-open
# ---------------------------------------------------------------------------


class TestDispatchTaskWrapper:
    def test_success_runs_async_and_returns_none(self) -> None:
        with patch(
            "app.workflows.reminder_dispatch._async_dispatch_due_reminders", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 3
            assert dispatch_due_reminders() is None
            mock_async.assert_awaited_once()

    def test_does_not_propagate_if_async_raises(self) -> None:
        with (
            patch(
                "app.workflows.reminder_dispatch._async_dispatch_due_reminders",
                new_callable=AsyncMock,
            ) as mock_async,
            patch("app.workflows.reminder_dispatch.logger.error") as mock_log,
        ):
            mock_async.side_effect = RuntimeError("DB caida")
            assert dispatch_due_reminders() is None
            mock_log.assert_called_once()


# ---------------------------------------------------------------------------
# Integración: despacho real
# ---------------------------------------------------------------------------


class FakeNotifier:
    """Notifier fake que registra las llamadas y devuelve el conteo de tokens."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_many(self, *, tokens: list[str], text: str) -> int:
        self.calls.append({"tokens": list(tokens), "text": text})
        return len(tokens)


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
    text: str,
    remind_at: datetime,
    status: ReminderStatus,
) -> Reminder:
    reminder = Reminder(user_id=user_id, text=text, remind_at=remind_at, status=status)
    session.add(reminder)
    await session.flush()
    await session.refresh(reminder)
    return reminder


async def _seed_token(session: AsyncSession, *, user_id: uuid.UUID, token: str) -> None:
    session.add(DeviceToken(user_id=user_id, platform=DevicePlatform.IOS, token=token))
    await session.flush()


@pytest.mark.integration
async def test_dispatch_only_due_marks_sent(db_session: AsyncSession) -> None:
    """Despacha SOLO los vencidos pending (``remind_at <= now``), los marca ``sent``."""
    now = datetime.now(UTC)
    user = await _seed_user(db_session)
    await _seed_token(db_session, user_id=user.id, token="dev-token-1")

    past = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Vencido",
        remind_at=now - timedelta(hours=1),
        status=ReminderStatus.PENDING,
    )
    at_now = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Justo ahora",
        remind_at=now,
        status=ReminderStatus.PENDING,
    )
    future = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Futuro",
        remind_at=now + timedelta(hours=1),
        status=ReminderStatus.PENDING,
    )
    already_sent = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Ya enviado",
        remind_at=now - timedelta(hours=2),
        status=ReminderStatus.SENT,
    )
    cancelled = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Cancelado",
        remind_at=now - timedelta(hours=2),
        status=ReminderStatus.CANCELLED,
    )

    notifier = FakeNotifier()
    dispatched = await _async_dispatch_due_reminders(session=db_session, now=now, notifier=notifier)

    # 2 vencidos pending (past + at_now); el borde <= incluye el exacto en ``now``.
    assert dispatched == 2

    await db_session.refresh(past)
    await db_session.refresh(at_now)
    await db_session.refresh(future)
    await db_session.refresh(already_sent)
    await db_session.refresh(cancelled)

    assert past.status == ReminderStatus.SENT
    assert at_now.status == ReminderStatus.SENT
    # Futuro intacto; ya-enviado/cancelado sin cambios.
    assert future.status == ReminderStatus.PENDING
    assert already_sent.status == ReminderStatus.SENT
    assert cancelled.status == ReminderStatus.CANCELLED

    # El notifier recibió los tokens del dueño, una vez por vencido (2 llamadas).
    assert len(notifier.calls) == 2
    for call in notifier.calls:
        assert call["tokens"] == ["dev-token-1"]


@pytest.mark.integration
async def test_dispatch_just_future_not_dispatched(db_session: AsyncSession) -> None:
    """Un recordatorio 1s a futuro (``remind_at > now``) NO se despacha (borde estricto)."""
    now = datetime.now(UTC)
    user = await _seed_user(db_session)
    just_future = await _seed_reminder(
        db_session,
        user_id=user.id,
        text="Casi",
        remind_at=now + timedelta(seconds=1),
        status=ReminderStatus.PENDING,
    )

    notifier = FakeNotifier()
    dispatched = await _async_dispatch_due_reminders(session=db_session, now=now, notifier=notifier)

    assert dispatched == 0
    await db_session.refresh(just_future)
    assert just_future.status == ReminderStatus.PENDING
    assert notifier.calls == []


@pytest.mark.integration
async def test_dispatch_isolated_tokens_per_user(db_session: AsyncSession) -> None:
    """El despacho de un recordatorio usa SOLO los tokens del dueño (aislamiento)."""
    now = datetime.now(UTC)
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    await _seed_token(db_session, user_id=owner.id, token="owner-tok")
    await _seed_token(db_session, user_id=other.id, token="other-tok")

    await _seed_reminder(
        db_session,
        user_id=owner.id,
        text="Del owner",
        remind_at=now - timedelta(minutes=5),
        status=ReminderStatus.PENDING,
    )

    notifier = FakeNotifier()
    dispatched = await _async_dispatch_due_reminders(session=db_session, now=now, notifier=notifier)

    assert dispatched == 1
    assert len(notifier.calls) == 1
    # Solo el token del owner, nunca el de otro usuario.
    assert notifier.calls[0]["tokens"] == ["owner-tok"]
