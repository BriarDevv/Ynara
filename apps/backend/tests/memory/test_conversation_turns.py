"""Tests del store de turnos de conversacion ``ConversationTurnStore`` (issue #209).

UNIT: validacion del schema ``ConversationTurnOut`` (rechaza ``BYTEA`` crudo).
INTEGRATION (``@pytest.mark.integration``, DB real): cifrado/descifrado,
orden por ``seq``, purga, y aislamiento por ``user_id`` (regla #3 / regla #4).

``conversation_turns`` es una tabla OPERATIVA, pero el ``content`` viaja cifrado
AES-256-GCM per-user igual que la memoria del moat: los tests de integracion
verifican que el blob en la DB es ``bytes`` (no plaintext) y que descifrar el blob
de otro usuario con la key ajena tira ``InvalidTag``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user
from app.enums import Mode, TurnRole
from app.memory.conversation_turns import ConversationTurnStore
from app.models.conversation_turn import ConversationTurn
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.conversation_turn import ConversationTurnCreate, ConversationTurnOut

# ---------------------------------------------------------------------------
# UNIT — schema strict
# ---------------------------------------------------------------------------


def test_out_rejects_raw_bytes_content() -> None:
    """``ConversationTurnOut`` con ``content=bytes`` -> ValidationError (strict).

    El wrapper debe pasar ``content`` ya descifrado como ``str``; el schema rechaza
    el ``BYTEA`` crudo (defensa en profundidad).
    """
    with pytest.raises(ValidationError):
        ConversationTurnOut(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            role=TurnRole.USER,
            content=b"\x00blob-cifrado-crudo",  # type: ignore[arg-type]
            seq=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )


def test_create_rejects_empty_content() -> None:
    """``ConversationTurnCreate`` con ``content=''`` -> ValidationError (min_length)."""
    with pytest.raises(ValidationError):
        ConversationTurnCreate(
            session_id=uuid.uuid4(),
            role=TurnRole.MODEL,
            content="",
            seq=1,
        )


# ---------------------------------------------------------------------------
# INTEGRATION — DB real
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_session(
    session: AsyncSession, *, user_id: uuid.UUID, mode: Mode = Mode.VIDA
) -> ChatSession:
    cs = ChatSession(user_id=user_id, mode=mode)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


@pytest.mark.integration
class TestConversationTurnStoreIntegration:
    """Tests de ``ConversationTurnStore`` contra la DB de tests (rollback al final)."""

    async def test_add_persists_encrypted_content(self, db_session: AsyncSession) -> None:
        """``add`` cifra el ``content``: el blob en la DB es bytes, NO plaintext."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        plaintext = "hola, soy un mensaje secreto del usuario"
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content=plaintext, seq=0)
        )

        # Lectura cruda del blob: debe ser bytes y NO contener el plaintext.
        raw = (
            await db_session.execute(
                select(ConversationTurn.content).where(ConversationTurn.session_id == cs.id)
            )
        ).scalar_one()
        assert isinstance(raw, bytes)
        assert plaintext.encode("utf-8") not in raw

        # El store descifra al leer.
        turns = await store.list_for_session(cs.id)
        assert len(turns) == 1
        assert turns[0].content == plaintext

    async def test_list_for_session_ordered_by_seq(self, db_session: AsyncSession) -> None:
        """``list_for_session`` devuelve los turnos ORDER BY ``seq`` ASC."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        # Insertar fuera de orden a proposito: seq 1 antes que seq 0.
        await store.add(
            ConversationTurnCreate(
                session_id=cs.id, role=TurnRole.MODEL, content="respuesta", seq=1
            )
        )
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content="pregunta", seq=0)
        )

        turns = await store.list_for_session(cs.id)
        assert [t.seq for t in turns] == [0, 1]
        assert turns[0].role == TurnRole.USER
        assert turns[0].content == "pregunta"
        assert turns[1].role == TurnRole.MODEL
        assert turns[1].content == "respuesta"

    async def test_purge_session_hard_deletes(self, db_session: AsyncSession) -> None:
        """``purge_session`` borra todos los turnos de la sesion; devuelve el rowcount."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content="uno", seq=0)
        )
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.MODEL, content="dos", seq=1)
        )

        purged = await store.purge_session(cs.id)
        assert purged == 2
        assert await store.list_for_session(cs.id) == []

    async def test_user_isolation(self, db_session: AsyncSession) -> None:
        """Cada user solo ve/purga sus turnos; el blob ajeno no descifra con su key."""
        user_a = await _seed_user(db_session)
        user_b = await _seed_user(db_session)
        cs_a = await _seed_session(db_session, user_id=user_a.id)
        cs_b = await _seed_session(db_session, user_id=user_b.id)
        store_a = ConversationTurnStore(db_session, user_a.id)
        store_b = ConversationTurnStore(db_session, user_b.id)

        await store_a.add(
            ConversationTurnCreate(
                session_id=cs_a.id, role=TurnRole.USER, content="dato de A", seq=0
            )
        )
        await store_b.add(
            ConversationTurnCreate(
                session_id=cs_b.id, role=TurnRole.USER, content="dato de B", seq=0
            )
        )

        # A no ve la sesion de B (filtra por user_id + session_id).
        assert await store_a.list_for_session(cs_b.id) == []
        # A purga la sesion de B -> 0 filas (no toca nada ajeno).
        assert await store_a.purge_session(cs_b.id) == 0
        # B sigue teniendo su turno.
        b_turns = await store_b.list_for_session(cs_b.id)
        assert len(b_turns) == 1
        assert b_turns[0].content == "dato de B"

        # El blob de B NO descifra con la key derivada de A (InvalidTag).
        raw_b = (
            await db_session.execute(
                select(ConversationTurn.content).where(ConversationTurn.session_id == cs_b.id)
            )
        ).scalar_one()
        with pytest.raises(InvalidTag):
            decrypt_for_user(user_a.id, raw_b)


@pytest.mark.integration
class TestListRecentForSession:
    """Tests de ``list_recent_for_session`` — variante eficiente para el historial del chat.

    Verifica que el LIMIT se aplica a nivel DB (solo llegan los últimos N), que el
    resultado viene en orden cronológico (ASC), y que el aislamiento user_id+session_id
    se respeta igual que en ``list_for_session``.
    """

    async def test_returns_last_n_in_asc_order(self, db_session: AsyncSession) -> None:
        """Con limit=3 y 5 turnos sembrados, devuelve los 3 últimos en orden ASC."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        # Sembrar 5 turnos en orden: seq 0..4
        contents = ["msg0", "msg1", "msg2", "msg3", "msg4"]
        for seq, content in enumerate(contents):
            role = TurnRole.USER if seq % 2 == 0 else TurnRole.MODEL
            await store.add(
                ConversationTurnCreate(session_id=cs.id, role=role, content=content, seq=seq)
            )

        turns = await store.list_recent_for_session(cs.id, limit=3)

        # Solo los últimos 3 (seq 2, 3, 4) en orden ASC.
        assert len(turns) == 3
        assert [t.seq for t in turns] == [2, 3, 4]
        assert [t.content for t in turns] == ["msg2", "msg3", "msg4"]

    async def test_returns_all_when_limit_exceeds_count(self, db_session: AsyncSession) -> None:
        """Cuando limit > número de turnos, devuelve todos en orden ASC."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        for seq in range(2):
            await store.add(
                ConversationTurnCreate(
                    session_id=cs.id,
                    role=TurnRole.USER if seq % 2 == 0 else TurnRole.MODEL,
                    content=f"t{seq}",
                    seq=seq,
                )
            )

        turns = await store.list_recent_for_session(cs.id, limit=10)
        assert len(turns) == 2
        assert [t.seq for t in turns] == [0, 1]

    async def test_empty_session_returns_empty_list(self, db_session: AsyncSession) -> None:
        """Sesión sin turnos devuelve lista vacía."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        turns = await store.list_recent_for_session(cs.id, limit=5)
        assert turns == []

    async def test_user_isolation_returns_only_own_turns(self, db_session: AsyncSession) -> None:
        """No devuelve turnos de otra sesión del mismo usuario ni de otro usuario."""
        user_a = await _seed_user(db_session)
        user_b = await _seed_user(db_session)
        cs_a = await _seed_session(db_session, user_id=user_a.id)
        cs_b = await _seed_session(db_session, user_id=user_b.id)
        store_a = ConversationTurnStore(db_session, user_a.id)
        store_b = ConversationTurnStore(db_session, user_b.id)

        for seq in range(3):
            await store_a.add(
                ConversationTurnCreate(
                    session_id=cs_a.id, role=TurnRole.USER, content=f"a{seq}", seq=seq
                )
            )
            await store_b.add(
                ConversationTurnCreate(
                    session_id=cs_b.id, role=TurnRole.USER, content=f"b{seq}", seq=seq
                )
            )

        # A no ve la sesión de B y B no ve la de A.
        assert await store_a.list_recent_for_session(cs_b.id, limit=10) == []
        assert await store_b.list_recent_for_session(cs_a.id, limit=10) == []

        # Cada uno ve solo sus propios turnos.
        turns_a = await store_a.list_recent_for_session(cs_a.id, limit=2)
        assert len(turns_a) == 2
        assert all(t.content.startswith("a") for t in turns_a)

    async def test_decrypts_content_correctly(self, db_session: AsyncSession) -> None:
        """El contenido devuelto está descifrado (no BYTEA crudo)."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        plaintext = "mensaje secreto descifrado"
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content=plaintext, seq=0)
        )

        turns = await store.list_recent_for_session(cs.id, limit=5)
        assert len(turns) == 1
        assert isinstance(turns[0].content, str)
        assert turns[0].content == plaintext


@pytest.mark.integration
class TestNextSeq:
    """Tests de ``next_seq`` — la lógica crítica anti-colisión del ``UNIQUE(session_id, seq)``.

    ``next_seq`` es ``COALESCE(MAX(seq), -1) + 1`` filtrado por ``user_id`` + ``session_id``.
    Es lo que previene el bug CRITICAL de #209 (seq hardcodeado a 0/1 colisionaba al reusar
    una sesión). HOY no tenía NINGÚN test directo del store: estos lo cubren.
    """

    async def test_next_seq_new_session_is_zero(self, db_session: AsyncSession) -> None:
        """Sesión nueva sin turnos -> 0 (``MAX(seq)`` NULL -> ``COALESCE(-1)+1``)."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        assert await store.next_seq(cs.id) == 0

    async def test_next_seq_is_monotonic_after_inserts(self, db_session: AsyncSession) -> None:
        """Tras insertar turnos, ``next_seq`` es ``MAX(seq)+1`` y avanza monotónico."""
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        # Insertar el turno 0 usando el seq que dicta el store.
        base = await store.next_seq(cs.id)
        assert base == 0
        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content="t0", seq=base)
        )
        # Tras un turno, el próximo seq es 1.
        assert await store.next_seq(cs.id) == 1

        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.MODEL, content="t1", seq=1)
        )
        # Tras dos turnos, el próximo es 2 (MAX(seq)=1 -> +1).
        assert await store.next_seq(cs.id) == 2

    async def test_next_seq_respects_max_not_count(self, db_session: AsyncSession) -> None:
        """``next_seq`` es ``MAX(seq)+1``, NO ``count``: un seq alto suelto lo refleja.

        Si se inserta un turno con ``seq=5`` (sin los intermedios), el próximo libre es
        6 — la lógica usa el máximo, no la cantidad de filas. Asegura que no haya
        colisión con el ``UNIQUE`` aunque la secuencia tenga huecos.
        """
        user = await _seed_user(db_session)
        cs = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        await store.add(
            ConversationTurnCreate(session_id=cs.id, role=TurnRole.USER, content="alto", seq=5)
        )
        assert await store.next_seq(cs.id) == 6

    async def test_next_seq_isolated_by_session(self, db_session: AsyncSession) -> None:
        """El ``next_seq`` de una sesión NO se contamina con los turnos de otra sesión.

        Dos sesiones del MISMO user: insertar turnos en una no mueve el ``next_seq`` de
        la otra (el query filtra por ``session_id``). Una sesión nueva sigue arrancando
        en 0 aunque otra ya tenga turnos.
        """
        user = await _seed_user(db_session)
        cs_a = await _seed_session(db_session, user_id=user.id)
        cs_b = await _seed_session(db_session, user_id=user.id)
        store = ConversationTurnStore(db_session, user.id)

        # Llenar la sesión A con 3 turnos.
        for seq in range(3):
            role = TurnRole.USER if seq % 2 == 0 else TurnRole.MODEL
            await store.add(
                ConversationTurnCreate(session_id=cs_a.id, role=role, content=f"a{seq}", seq=seq)
            )

        # A avanzó a 3; B (sin turnos) sigue en 0: no se contaminó.
        assert await store.next_seq(cs_a.id) == 3
        assert await store.next_seq(cs_b.id) == 0

    async def test_next_seq_isolated_by_user(self, db_session: AsyncSession) -> None:
        """El ``next_seq`` filtra también por ``user_id``: el de un user no ve filas ajenas.

        Aunque dos users no compartirían un ``session_id`` real, el query filtra por
        AMBOS (``user_id`` **y** ``session_id``): un store ligado a otro user nunca
        cuenta turnos que no le pertenecen (aislamiento estructural).
        """
        user_a = await _seed_user(db_session)
        user_b = await _seed_user(db_session)
        cs_a = await _seed_session(db_session, user_id=user_a.id)
        store_a = ConversationTurnStore(db_session, user_a.id)
        store_b = ConversationTurnStore(db_session, user_b.id)

        await store_a.add(
            ConversationTurnCreate(session_id=cs_a.id, role=TurnRole.USER, content="de A", seq=0)
        )

        # A ve su turno (próximo = 1); B, ligado a otro user, ve 0 para esa misma sesión.
        assert await store_a.next_seq(cs_a.id) == 1
        assert await store_b.next_seq(cs_a.id) == 0
