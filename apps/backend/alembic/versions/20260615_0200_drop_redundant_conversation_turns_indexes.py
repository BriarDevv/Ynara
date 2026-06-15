"""indices de conversation_turns: reemplazar los 3 parciales por un compuesto.

Tabla OPERATIVA (no sagrada, regla #3). La migracion original creaba 3 indices
parciales (``user_id``; ``session_id``; ``(session_id, seq)``) que NO matchean el
patron real de queries del store —todas filtran por ``user_id`` Y ``session_id``
(next_seq, list_for_session, purge_session)— y ademas dos eran redundantes con el
indice implicito del ``UNIQUE(session_id, seq)``.

Se reemplazan por UN indice compuesto ``(user_id, session_id, seq)`` que sirve
exacto ese patron (incl. el ``MAX(seq)`` de next_seq y el ``ORDER BY seq``), y cuyo
prefijo ``(user_id)`` cubre el cascade-delete por usuario. El ``UNIQUE(session_id,
seq)`` (constraint, intacto) sigue cubriendo el acceso por sesion y su cascade.
Neto: 3 indices -> 1, mejor selectividad y menos overhead de escritura por INSERT.
El downgrade recrea los 3 originales (round-trip limpio).

Revision ID: b7e2f4a16c9d
Revises: c4e8a1d50b93
Create Date: 2026-06-15 02:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2f4a16c9d"
down_revision: str | None = "c4e8a1d50b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reemplaza los 3 indices parciales por uno compuesto que matchea el patron
    # real de queries: WHERE user_id=? AND session_id=? [ORDER BY seq] / MAX(seq).
    op.drop_index("ix_conversation_turns_session_id_seq", table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_session_id"), table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_user_id"), table_name="conversation_turns")
    op.create_index(
        "ix_conversation_turns_user_id_session_id_seq",
        "conversation_turns",
        ["user_id", "session_id", "seq"],
        unique=False,
    )


def downgrade() -> None:
    # Recrea los 3 indices originales tal cual la migracion inicial (round-trip).
    op.drop_index("ix_conversation_turns_user_id_session_id_seq", table_name="conversation_turns")
    op.create_index(
        op.f("ix_conversation_turns_session_id"),
        "conversation_turns",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_turns_user_id"),
        "conversation_turns",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_turns_session_id_seq",
        "conversation_turns",
        ["session_id", "seq"],
        unique=False,
    )
