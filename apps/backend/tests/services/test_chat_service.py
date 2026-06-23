"""Tests unit de ``ChatService._load_history``.

Foco: mapeo de roles (USER→user, MODEL→assistant) y fallback defensivo para roles
inesperados. Usa ``ConversationTurnStore`` mockeado para no tocar DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.enums import TurnRole
from app.llm.schemas import ChatMessage
from app.schemas.conversation_turn import ConversationTurnOut

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _turn(
    role: TurnRole,
    content: str,
    seq: int = 0,
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> ConversationTurnOut:
    """Construye un ``ConversationTurnOut`` mínimo para los tests."""
    return ConversationTurnOut(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
        role=role,
        content=content,
        seq=seq,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _make_service(
    user_id: uuid.UUID | None = None,
) -> tuple[object, uuid.UUID]:
    """Instancia un ``ChatService`` con deps dummy (no se llama nada real)."""
    from app.services.chat import ChatService

    uid = user_id or uuid.uuid4()
    service = ChatService(
        session=MagicMock(),
        user_id=uid,
        llm_client=MagicMock(),
        embedder=MagicMock(),
        reranker=MagicMock(),
    )
    return service, uid


# ---------------------------------------------------------------------------
# Tests de mapeo de rol y fallback defensivo
# ---------------------------------------------------------------------------


async def test_load_history_maps_user_and_model_roles() -> None:
    """USER→'user' y MODEL→'assistant' en el ChatMessage resultante."""
    service, _ = _make_service()

    turns = [
        _turn(TurnRole.USER, "pregunta del user", seq=0),
        _turn(TurnRole.MODEL, "respuesta del modelo", seq=1),
    ]

    chat_session = MagicMock()
    chat_session.id = uuid.uuid4()

    with patch("app.services.chat.ConversationTurnStore") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.list_recent_for_session = AsyncMock(return_value=turns)
        mock_store_cls.return_value = store_instance

        result = await service._load_history(chat_session)

    assert len(result) == 2
    assert result[0] == ChatMessage(role="user", content="pregunta del user")
    assert result[1] == ChatMessage(role="assistant", content="respuesta del modelo")


async def test_load_history_fallback_on_unknown_role() -> None:
    """Rol desconocido cae al fallback 'assistant' (no lanza KeyError)."""
    service, _ = _make_service()

    # Fabricar un turno con rol que NO está en el mapeo (simulando un dato inesperado).
    bad_turn = _turn(TurnRole.USER, "contenido", seq=0)
    bad_turn_with_unknown = bad_turn.model_copy(update={"role": "UNKNOWN_ROLE"})  # type: ignore[arg-type]

    chat_session = MagicMock()
    chat_session.id = uuid.uuid4()

    with patch("app.services.chat.ConversationTurnStore") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.list_recent_for_session = AsyncMock(return_value=[bad_turn_with_unknown])
        mock_store_cls.return_value = store_instance

        # No debe lanzar KeyError.
        result = await service._load_history(chat_session)

    assert len(result) == 1
    assert result[0].role == "assistant"


async def test_load_history_empty_session_returns_empty() -> None:
    """Primer turno de la sesión (sin turnos previos) devuelve lista vacía."""
    service, _ = _make_service()

    chat_session = MagicMock()
    chat_session.id = uuid.uuid4()

    with patch("app.services.chat.ConversationTurnStore") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.list_recent_for_session = AsyncMock(return_value=[])
        mock_store_cls.return_value = store_instance

        result = await service._load_history(chat_session)

    assert result == []


async def test_load_history_calls_list_recent_with_correct_limit() -> None:
    """Verifica que se llama a ``list_recent_for_session`` con el HISTORY_MAX_MESSAGES correcto."""
    from app.services.chat import _HISTORY_MAX_MESSAGES

    service, _ = _make_service()

    chat_session = MagicMock()
    session_id = uuid.uuid4()
    chat_session.id = session_id

    with patch("app.services.chat.ConversationTurnStore") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.list_recent_for_session = AsyncMock(return_value=[])
        mock_store_cls.return_value = store_instance

        await service._load_history(chat_session)

    store_instance.list_recent_for_session.assert_called_once_with(
        session_id, _HISTORY_MAX_MESSAGES
    )


async def test_load_history_preserves_chronological_order() -> None:
    """El historial se devuelve en el mismo orden que el store (cronológico)."""
    service, _ = _make_service()

    turns = [
        _turn(TurnRole.USER, "primera pregunta", seq=0),
        _turn(TurnRole.MODEL, "primera respuesta", seq=1),
        _turn(TurnRole.USER, "segunda pregunta", seq=2),
        _turn(TurnRole.MODEL, "segunda respuesta", seq=3),
    ]

    chat_session = MagicMock()
    chat_session.id = uuid.uuid4()

    with patch("app.services.chat.ConversationTurnStore") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.list_recent_for_session = AsyncMock(return_value=turns)
        mock_store_cls.return_value = store_instance

        result = await service._load_history(chat_session)

    assert [m.content for m in result] == [
        "primera pregunta",
        "primera respuesta",
        "segunda pregunta",
        "segunda respuesta",
    ]
    assert [m.role for m in result] == ["user", "assistant", "user", "assistant"]
