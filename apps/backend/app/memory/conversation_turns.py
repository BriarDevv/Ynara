"""Store cifrado de turnos crudos de conversación (``conversation_turns``).

Espejo de los stores de memoria (``SemanticMemoryStore`` /
``EpisodicMemoryStore``), pero sobre una tabla **OPERATIVA** (no sagrada): un
buffer transitorio que el worker episódico (``consolidate_session``) lee al
cerrar la sesión y luego purga. Aun siendo operativa, el ``content`` viaja
cifrado AES-256-GCM per-user (regla #4: cero PII en claro en la DB) — exactamente
como ``semantic.content`` / ``episodic.summary``.

``ConversationTurnStore`` se construye **por request** ligando ``user_id`` en el
``__init__`` (la key de cifrado se deriva de ``user_id``): aislamiento estructural
(igual que los stores de memoria). El ``user_id`` nunca viaja como argumento de
método, así toda fila queda forzosamente atada al usuario del store.

Pipeline:

- ``next_seq``: devuelve el próximo ``seq`` libre de una sesión
  (``MAX(seq)+1``, 0 si la sesión no tiene turnos). El caller lo usa para
  numerar turnos sin colisionar con el ``UniqueConstraint(session_id, seq)``
  al reusar una sesión existente (issue #209).
- ``add``: cifra el plaintext con ``encrypt_for_user`` y hace ``flush`` (NO
  ``commit``): el commit lo da el endpoint (``ChatService.run_turn``) en la MISMA
  transacción que la ``ChatSession``, así turnos + sesión son atómicos.
- ``list_for_session``: trae TODOS los turnos de una sesión ORDER BY ``seq`` ASC
  y los descifra in-process ANTES de construir el ``Out`` strict (que rechaza
  ``BYTEA``). Lo usa el worker episódico que necesita el transcript completo.
- ``list_recent_for_session``: variante eficiente para el historial del chat: trae
  solo los últimos ``limit`` turnos (ORDER BY seq DESC LIMIT) y los devuelve en
  orden cronológico. Para sesiones largas evita descifrar cientos de filas que el
  router descartaría igual.
- ``purge_session``: hard-delete de los turnos de una sesión (lo llama el worker
  tras consolidar). NO descifra: borrar el ``BYTEA`` no requiere leerlo en claro.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user, encrypt_for_user
from app.models.conversation_turn import ConversationTurn
from app.schemas.conversation_turn import ConversationTurnCreate, ConversationTurnOut


class ConversationTurnStore:
    """Store por-request de ``conversation_turns``, ligado a un ``user_id``.

    El ``user_id`` se liga en el constructor (deriva la key de cifrado): todo
    query filtra por ``self._user_id`` y todo descifrado usa esa misma identidad.
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def add(self, payload: ConversationTurnCreate) -> None:
        """Persiste un turno: cifra el ``content`` plaintext e INSERTA (flush, sin commit).

        El commit lo da el caller (``ChatService.run_turn``) en la misma transacción que
        la ``ChatSession``: turnos + sesión se persisten juntos o nada.
        """
        blob = encrypt_for_user(self._user_id, payload.content)
        row = ConversationTurn(
            user_id=self._user_id,
            session_id=payload.session_id,
            role=payload.role,
            content=blob,
            seq=payload.seq,
        )
        self._session.add(row)
        await self._session.flush()

    async def next_seq(self, session_id: UUID) -> int:
        """Devuelve el próximo ``seq`` libre de una sesión (``MAX(seq)+1``).

        Si la sesión no tiene turnos, ``MAX(seq)`` es ``NULL``; el ``COALESCE`` a
        -1 hace que el primer turno arranque en 0. El caller numera el turno user
        con ``base`` y el del modelo con ``base+1``, así un segundo turno sobre una
        sesión reusada NO colisiona con ``UniqueConstraint(session_id, seq)``
        (issue #209). Filtra por ``user_id`` **y** ``session_id`` (aislamiento
        estructural), igual que el resto del store.
        """
        stmt = select(func.coalesce(func.max(ConversationTurn.seq), -1) + 1).where(
            ConversationTurn.user_id == self._user_id,
            ConversationTurn.session_id == session_id,
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def list_for_session(self, session_id: UUID) -> list[ConversationTurnOut]:
        """Lista TODOS los turnos de una sesión del usuario, ORDER BY ``seq`` ASC.

        Filtra por ``user_id`` **y** ``session_id`` (aislamiento estructural): solo
        turnos del usuario del store. Descifra fila por fila ANTES de construir el
        ``Out`` strict. Lo usa el worker episódico para reconstruir el transcript
        completo de la sesión (necesita todos los turnos, no solo los últimos N).
        Para el historial del chat de producción usar ``list_recent_for_session``
        (más eficiente: solo descifra los turnos que el router va a usar).
        """
        stmt = (
            select(ConversationTurn)
            .where(
                ConversationTurn.user_id == self._user_id,
                ConversationTurn.session_id == session_id,
            )
            .order_by(ConversationTurn.seq.asc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [
            self._to_out(row, plaintext=decrypt_for_user(self._user_id, row.content))
            for row in rows
        ]

    async def list_recent_for_session(
        self, session_id: UUID, limit: int
    ) -> list[ConversationTurnOut]:
        """Lista los últimos ``limit`` turnos de una sesión, en orden cronológico.

        Diseñado para el historial del chat (``ChatService._load_history``): hace
        ``ORDER BY seq DESC LIMIT :limit`` a nivel DB (solo descifra las filas que
        el router va a usar), luego invierte la lista para devolver orden
        cronológico (ASC). Para sesiones largas —modo vida acumula turnos hasta
        cerrar— evita descifrar cientos de filas que ``trim_history_to_budget``
        descartaría de todas formas.

        A diferencia de ``list_for_session`` (que trae el transcript completo para
        el worker episódico), este método es intencionalmente acotado: solo devuelve
        los últimos ``limit`` turnos contiguos más recientes.

        Filtra por ``user_id`` **y** ``session_id`` (aislamiento estructural):
        mismo patrón que el resto del store.
        """
        stmt = (
            select(ConversationTurn)
            .where(
                ConversationTurn.user_id == self._user_id,
                ConversationTurn.session_id == session_id,
            )
            .order_by(ConversationTurn.seq.desc())
            .limit(limit)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        # Descifrar e invertir: la DB devuelve los más recientes primero (DESC);
        # el modelo espera orden cronológico (ASC) para entender la conversación.
        rows.reverse()
        return [
            self._to_out(row, plaintext=decrypt_for_user(self._user_id, row.content))
            for row in rows
        ]

    async def purge_session(self, session_id: UUID) -> int:
        """Hard-delete de todos los turnos de una sesión del usuario. Devuelve el rowcount.

        Lo llama el worker episódico tras consolidar la sesión: los turnos crudos
        son transitorios (su resumen ya quedó en ``episodic_memory``). El ``WHERE``
        filtra por ``user_id`` **y** ``session_id`` (aislamiento estructural). NO
        descifra: borrar el ``BYTEA`` no requiere leerlo en claro (regla #4). Solo
        hace ``flush``: el commit lo da el worker en la misma transacción que el
        resumen episódico (summary + purge atómicos).
        """
        stmt = sa_delete(ConversationTurn).where(
            ConversationTurn.user_id == self._user_id,
            ConversationTurn.session_id == session_id,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    @staticmethod
    def _to_out(row: ConversationTurn, *, plaintext: str) -> ConversationTurnOut:
        """Construye el ``Out`` con el ``content`` ya descifrado (nunca el ``BYTEA``)."""
        return ConversationTurnOut(
            id=row.id,
            user_id=row.user_id,
            session_id=row.session_id,
            role=row.role,
            content=plaintext,
            seq=row.seq,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
