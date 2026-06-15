"""Modelo SQLAlchemy de turno de conversación: ``conversation_turns``.

Tabla **OPERATIVA**, no sagrada (regla #3): es un buffer transitorio de los
turnos crudos (user/modelo) de una sesión, la **fuente** que el worker episódico
(``consolidate_session``) lee al cerrar la sesión para resumir y persistir en
``episodic_memory`` (sagrada). Una vez consolidados, los turnos se **purgan**
(``ConversationTurnStore.purge_session``): no son almacenamiento de largo plazo.

Append-only: un turno se inserta una vez y nunca se modifica (se consolida y se
purga, no se edita). Por eso ``updated_at`` (heredado del ``TimestampMixin``)
siempre iguala a ``created_at``; se conserva por uniformidad con los ``*Out`` de
las 3 capas de memoria —todos exponen ``updated_at``—, no porque los turnos se
actualicen.

A pesar de ser operativa, el ``content`` viaja **cifrado AES-256-GCM per-user**
(``BYTEA``) vía ``app/core/crypto.py``, igual que ``semantic_memory.content`` /
``episodic_memory.summary`` (regla #4: cero PII en claro en la DB). El cifrado lo
hace el store (``ConversationTurnStore``), no el modelo: aquí solo se declara la
columna como ``LargeBinary``.

Orden e idempotencia: ``seq`` es un entero monotónico por sesión (0 = primer
turno del usuario, 1 = primera respuesta del modelo, ...). El
``UniqueConstraint(session_id, seq)`` impide insertar dos turnos con el mismo
orden en la misma sesión. El índice compuesto ``(user_id, session_id, seq)``
sirve el patrón real de queries del store —todas filtran por ``user_id`` +
``session_id`` (next_seq, list_for_session, purge_session) y ordenan por
``seq``— y su prefijo ``(user_id)`` cubre el cascade-delete por usuario; el
índice implícito del UNIQUE cubre el de sesión.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import TurnRole, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

__all__ = ["ConversationTurn"]


class ConversationTurn(UUIDPKMixin, TimestampMixin, Base):
    """Un turno crudo (user o modelo) de una sesión de chat.

    Buffer transitorio: el worker episódico lo lee ordenado por ``seq`` al
    cerrar la sesión, resume el transcript y luego purga estas filas. El
    ``content`` está cifrado per-user (lo cifra/descifra el store).
    """

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_conversation_turns_session_id_seq"),
        # Índice único de acceso: matchea WHERE user_id=? AND session_id=? (next_seq,
        # list_for_session, purge_session) y ordena por seq. Reemplaza los 3 índices
        # parciales originales (auditoría backend). El prefijo (user_id) cubre el FK
        # cascade por usuario; el UNIQUE(session_id, seq) cubre el de sesión.
        Index("ix_conversation_turns_user_id_session_id_seq", "user_id", "session_id", "seq"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[TurnRole] = mapped_column(
        Enum(TurnRole, name="turn_role_enum", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
