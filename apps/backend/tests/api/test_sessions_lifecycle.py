"""Tests de ciclo de vida de ChatSession via resolve_chat_session.

Todos los tests son ``integration`` y usan ``db_session`` (rollback al
final; nunca persisten entre tests). Se necesita TEST_DATABASE_URL apuntando
a la DB de tests dedicada.

Casos cubiertos:
- Crear nueva sesión (session_id None) → ChatSession con user_id+mode, id asignado.
- Lookup OK (mismo user) → devuelve la misma instancia (mismo id).
- session_id de otro user → 404 (aislamiento, sin oráculo de existencia ajena).
- session_id inexistente → 404.
- mode mismatch → 409.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._sessions import resolve_chat_session
from app.enums import Mode
from app.models.user import User


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    return user


# ---------- crear sesión nueva ----------


@pytest.mark.integration
async def test_create_session_when_session_id_is_none(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)

    cs = await resolve_chat_session(
        db_session,
        user_id=user.id,
        session_id=None,
        mode=Mode.PRODUCTIVIDAD,
    )

    assert cs.id is not None
    assert cs.user_id == user.id
    assert cs.mode == Mode.PRODUCTIVIDAD


# ---------- lookup OK ----------


@pytest.mark.integration
async def test_lookup_existing_session_same_user(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)

    cs_created = await resolve_chat_session(
        db_session,
        user_id=user.id,
        session_id=None,
        mode=Mode.ESTUDIO,
    )

    cs_looked_up = await resolve_chat_session(
        db_session,
        user_id=user.id,
        session_id=cs_created.id,
        mode=Mode.ESTUDIO,
    )

    assert cs_looked_up.id == cs_created.id


# ---------- aislamiento: sesión de otro usuario ----------


@pytest.mark.integration
async def test_session_of_other_user_raises_404(db_session: AsyncSession) -> None:
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)

    cs = await resolve_chat_session(
        db_session,
        user_id=owner.id,
        session_id=None,
        mode=Mode.BIENESTAR,
    )

    with pytest.raises(HTTPException) as exc_info:
        await resolve_chat_session(
            db_session,
            user_id=intruder.id,
            session_id=cs.id,
            mode=Mode.BIENESTAR,
        )

    assert exc_info.value.status_code == 404


# ---------- sesión inexistente ----------


@pytest.mark.integration
async def test_nonexistent_session_raises_404(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    nonexistent_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_chat_session(
            db_session,
            user_id=user.id,
            session_id=nonexistent_id,
            mode=Mode.VIDA,
        )

    assert exc_info.value.status_code == 404


# ---------- mode mismatch ----------


@pytest.mark.integration
async def test_mode_mismatch_raises_409(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)

    cs = await resolve_chat_session(
        db_session,
        user_id=user.id,
        session_id=None,
        mode=Mode.PRODUCTIVIDAD,
    )

    with pytest.raises(HTTPException) as exc_info:
        await resolve_chat_session(
            db_session,
            user_id=user.id,
            session_id=cs.id,
            mode=Mode.ESTUDIO,
        )

    assert exc_info.value.status_code == 409
