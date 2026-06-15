"""Tests del enqueue episodico post-commit en ``POST /v1/sessions/{id}/close`` (issue #209).

Todos ``integration`` (el endpoint commitea). Verifican que ``close_session``:
- encola ``consolidate_session.delay(...)`` SOLO en el primer cierre real (con los
  kwargs JSON correctos: user_id / session_id / mode),
- NO re-encola en un segundo cierre (idempotente),
- fail-open: si el ``.delay()`` tira (broker caido), el close devuelve 200 igual.

Mismo andamiaje que ``test_sessions_close.py``: ``ASGITransport`` + override de
``get_db``; ``consolidate_session`` se parchea en ``app.api.v1.sessions``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.enums import Mode
from app.main import app
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, *, user_id: uuid.UUID, mode: Mode) -> ChatSession:
    cs = ChatSession(user_id=user_id, mode=mode)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
    await session.commit()


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_close_enqueues_consolidate_session(db_session: AsyncSession) -> None:
    """El primer cierre encola consolidate_session con los kwargs JSON correctos."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.BIENESTAR)

    client = await _client(db_session)
    try:
        with patch("app.api.v1.sessions.consolidate_session") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                resp = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))

        assert resp.status_code == 200
        mock_task.delay.assert_called_once()
        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs == {
            "user_id": str(user.id),
            "session_id": str(cs.id),
            "mode": "bienestar",
        }
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_second_close_does_not_re_enqueue(db_session: AsyncSession) -> None:
    """Cerrar dos veces encola SOLO una vez (la 2da es idempotente, no re-dispara)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        with patch("app.api.v1.sessions.consolidate_session") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                first = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))
                second = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))

        assert first.status_code == 200
        assert second.status_code == 200
        # El enqueue ocurrio SOLO en el primer cierre real.
        mock_task.delay.assert_called_once()
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_close_enqueue_failure_does_not_break_close(db_session: AsyncSession) -> None:
    """Si consolidate_session.delay lanza (broker caido), el close sigue 200 (fail-open)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    client = await _client(db_session)
    try:
        with patch("app.api.v1.sessions.consolidate_session") as mock_task:
            mock_task.delay = MagicMock(side_effect=RuntimeError("broker down"))
            async with client:
                resp = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))

        # 200 pese al fallo del enqueue: el cierre ya commiteo el ended_at.
        assert resp.status_code == 200
        assert resp.json()["ended_at"] is not None
        mock_task.delay.assert_called_once()
        # El ended_at quedo persistido pese al fallo del enqueue.
        await db_session.refresh(cs)
        assert cs.ended_at is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_close_enqueue_operational_error_fail_open(db_session: AsyncSession) -> None:
    """Fail-open ante un ``OperationalError`` del broker: el close sigue 200, ended_at persiste.

    El ``except Exception`` del endpoint atrapa cualquier fallo del ``.delay()`` (no
    solo ``RuntimeError``): un ``OperationalError`` (broker/redis inalcanzable) NO
    rompe el cierre — la consolidación es eventual, el ``ended_at`` ya se commiteó.
    """
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user_id=user.id, mode=Mode.VIDA)

    boom = OperationalError("ENQUEUE", params=None, orig=Exception("broker unreachable"))
    client = await _client(db_session)
    try:
        with patch("app.api.v1.sessions.consolidate_session") as mock_task:
            mock_task.delay = MagicMock(side_effect=boom)
            async with client:
                resp = await client.post(f"/v1/sessions/{cs.id}/close", headers=_bearer(user.id))

        assert resp.status_code == 200
        assert resp.json()["ended_at"] is not None
        mock_task.delay.assert_called_once()
        await db_session.refresh(cs)
        assert cs.ended_at is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)
