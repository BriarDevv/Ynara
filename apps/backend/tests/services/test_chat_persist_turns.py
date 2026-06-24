"""Test de integración del retry de ``ChatService._persist_turns`` (MEM-SACRED-01).

Una colisión de ``seq`` (TOCTOU entre ``next_seq`` y el flush del ``add``, posible con
dos turnos concurrentes sobre la MISMA sesión) NO debe reventar el turno con un 500: el
``UniqueConstraint(session_id, seq)`` es el guardián de última instancia y
``_persist_turns`` reintenta con un ``seq`` fresco en un savepoint.

Corre contra la DB de tests real (``db_session`` con savepoint). La colisión se inyecta
haciendo que ``next_seq`` devuelva un ``seq`` ya tomado en la 1ra tentativa.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode, TurnRole
from app.llm.schemas import ChatResponse
from app.memory.conversation_turns import ConversationTurnStore
from app.models.conversation_turn import ConversationTurn
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.chat import ChatHttpRequest
from app.schemas.conversation_turn import ConversationTurnCreate
from app.services.chat import ChatService

pytestmark = pytest.mark.integration


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(session: AsyncSession, user_id) -> ChatSession:
    cs = ChatSession(user_id=user_id, mode=Mode.PRODUCTIVIDAD)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


async def test_persist_turns_retries_on_seq_collision(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una colisión de ``seq`` se reintenta con un ``seq`` fresco en vez de propagar 500."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user.id)

    # Un turno ya ocupa seq=0 (simula el turno de un request concurrente que ganó la carrera).
    seed_store = ConversationTurnStore(db_session, user.id)
    await seed_store.add(
        ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content="previo", seq=0)
    )

    # next_seq miente en la 1ra tentativa (devuelve 0, ya tomado -> colisión); luego el real.
    real_next_seq = ConversationTurnStore.next_seq
    state = {"calls": 0}

    async def flaky_next_seq(self: ConversationTurnStore, session_id) -> int:
        state["calls"] += 1
        if state["calls"] == 1:
            return 0  # colisión deliberada: seq=0 ya existe
        return await real_next_seq(self, session_id)

    monkeypatch.setattr(ConversationTurnStore, "next_seq", flaky_next_seq)

    service = ChatService(
        session=db_session,
        user_id=user.id,
        llm_client=MagicMock(),
        embedder=MagicMock(),
        reranker=MagicMock(),
    )
    body = ChatHttpRequest(text="hola", mode=Mode.PRODUCTIVIDAD)
    resp = ChatResponse(text="respuesta", session_id=str(cs.id), finish_reason="stop")

    # NO debe lanzar (antes del fix: IntegrityError -> 500 + turno perdido).
    await service._persist_turns(cs, body=body, resp=resp)

    # Reintentó con seq fresco: 3 turnos (previo en 0 + user en 1 + model en 2).
    total = await db_session.scalar(
        select(func.count())
        .select_from(ConversationTurn)
        .where(ConversationTurn.session_id == cs.id)
    )
    assert total == 3, "los 2 turnos se persistieron tras el retry, sin perder el previo"
    assert state["calls"] >= 2, "hubo al menos un reintento tras la colisión"


async def test_persist_turns_happy_path_no_collision(db_session: AsyncSession) -> None:
    """Sin colisión, persiste los 2 turnos en la 1ra tentativa (seq base / base+1)."""
    user = await _seed_user(db_session)
    cs = await _seed_session(db_session, user.id)

    service = ChatService(
        session=db_session,
        user_id=user.id,
        llm_client=MagicMock(),
        embedder=MagicMock(),
        reranker=MagicMock(),
    )
    body = ChatHttpRequest(text="hola", mode=Mode.PRODUCTIVIDAD)
    resp = ChatResponse(text="respuesta", session_id=str(cs.id), finish_reason="stop")

    await service._persist_turns(cs, body=body, resp=resp)

    rows = (
        await db_session.execute(
            select(ConversationTurn.seq, ConversationTurn.role)
            .where(ConversationTurn.session_id == cs.id)
            .order_by(ConversationTurn.seq.asc())
        )
    ).all()
    assert [(r.seq, r.role) for r in rows] == [(0, TurnRole.USER), (1, TurnRole.MODEL)]
