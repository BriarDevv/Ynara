"""Tests E2E de la persistencia de turnos en ``/v1/chat`` (issue #209).

Todos ``integration`` (el endpoint commitea contra la DB de tests). Verifican que
``ChatService.run_turn`` persiste los 2 turnos (user seq=0 / model seq=1) cifrados en el
MISMO commit que la ``ChatSession``, y que NO los persiste si el turno DEGRADO.

Mismo andamiaje que ``test_chat.py``: ``ASGITransport`` + override de ``get_db`` y
de los clientes Fake; ``consolidate_turn`` se parchea (no hay Redis).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_llm_client, get_reranker
from app.core.security import create_access_token
from app.enums import TurnRole
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult
from app.main import app
from app.memory.conversation_turns import ConversationTurnStore
from app.models.conversation_turn import ConversationTurn
from app.models.user import User

pytestmark = pytest.mark.integration


def _completion(
    *, text: str = "hola", finish_reason: str = "stop", model_name: str = "gemma4"
) -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason=finish_reason,
        tool_calls=[],
        prompt_tokens=10,
        completion_tokens=5,
        model_name=model_name,
        latency_ms=42.0,
    )


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
    await session.commit()


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(
    db_session: AsyncSession, *, llm_client: FakeLlmClient
) -> AsyncIterator[httpx.AsyncClient]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: llm_client
    app.dependency_overrides[get_embedder] = FakeEmbeddingClient
    app.dependency_overrides[get_reranker] = FakeReranker
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Happy path: 2 turnos cifrados persistidos en el mismo commit
# ---------------------------------------------------------------------------


async def test_chat_persists_two_encrypted_turns(db_session: AsyncSession) -> None:
    """Un turno OK persiste user(seq=0) + model(seq=1) cifrados en la misma sesion."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola, todo bien?", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola Ynara", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        session_id = uuid.UUID(resp.json()["session_id"])

        # Blob crudo: 2 filas, content en bytes (no plaintext).
        rows = list(
            (
                await db_session.execute(
                    select(ConversationTurn)
                    .where(ConversationTurn.session_id == session_id)
                    .order_by(ConversationTurn.seq.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert isinstance(rows[0].content, bytes)
        assert b"hola Ynara" not in rows[0].content

        # Descifrado via el store: orden + roles + contenido correctos.
        store = ConversationTurnStore(db_session, user.id)
        turns = await store.list_for_session(session_id)
        assert [t.seq for t in turns] == [0, 1]
        assert turns[0].role == TurnRole.USER
        assert turns[0].content == "hola Ynara"
        assert turns[1].role == TurnRole.MODEL
        assert turns[1].content == "hola, todo bien?"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Multi-turno sobre una sesion REUSADA: seq monotonico, sin colision UNIQUE
# ---------------------------------------------------------------------------


async def test_chat_multi_turn_same_session_increments_seq(db_session: AsyncSession) -> None:
    """2 POST a la MISMA sesion (session_id en el body) persisten 4 turnos.

    Regresion del bug CRITICAL (issue #209): con ``seq`` hardcodeado a 0/1, el
    segundo turno reinsertaba seq=0/1 y violaba ``UniqueConstraint(session_id, seq)``
    en el flush -> IntegrityError -> rollback -> 500 y turno perdido. Con el seq
    POR SESION (``MAX(seq)+1``), ambos turnos dan 200, la secuencia es [0,1,2,3]
    monotonica, los roles alternan user/model y los 4 turnos quedan persistidos.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="primera respuesta", model_name="gemma4"))
    fake.queue_result(_completion(text="segunda respuesta", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            first = await client.post(
                "/v1/chat",
                json={"text": "hola Ynara", "mode": "vida"},
                headers=_bearer(user.id),
            )
            assert first.status_code == 200
            session_id = first.json()["session_id"]

            # Segundo turno REUSANDO la sesion (mismo session_id en el body).
            second = await client.post(
                "/v1/chat",
                json={"text": "segunda pregunta", "mode": "vida", "session_id": session_id},
                headers=_bearer(user.id),
            )
            # Antes del fix esto daba 500 (IntegrityError en el flush).
            assert second.status_code == 200
            assert second.json()["session_id"] == session_id

        session_uuid = uuid.UUID(session_id)
        # Los 4 turnos persistidos, ordenados por seq: secuencia monotonica.
        store = ConversationTurnStore(db_session, user.id)
        turns = await store.list_for_session(session_uuid)
        assert [t.seq for t in turns] == [0, 1, 2, 3]
        # Roles alternados user/model a lo largo de la sesion.
        assert [t.role for t in turns] == [
            TurnRole.USER,
            TurnRole.MODEL,
            TurnRole.USER,
            TurnRole.MODEL,
        ]
        # Contenido de cada turno (user pregunta / model responde).
        assert [t.content for t in turns] == [
            "hola Ynara",
            "primera respuesta",
            "segunda pregunta",
            "segunda respuesta",
        ]
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Degradado: no se persiste ningun turno
# ---------------------------------------------------------------------------


async def test_chat_degraded_persists_no_turns(db_session: AsyncSession) -> None:
    """Un turno con finish_reason='degraded' NO persiste turnos (ni consolida)."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(
        _completion(text="respuesta degradada", finish_reason="degraded", model_name="qwen")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.services.chat.consolidate_turn") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "hola", "mode": "productividad"},
                    headers=_bearer(user.id),
                )
        assert resp.status_code == 200
        assert resp.json()["finish_reason"] == "degraded"
        session_id = uuid.UUID(resp.json()["session_id"])

        # Sin turnos persistidos.
        count = (
            (
                await db_session.execute(
                    select(ConversationTurn).where(ConversationTurn.session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        assert count == []
        # Tampoco se encolo consolidate_turn (turno degradado).
        mock_task.delay.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)
