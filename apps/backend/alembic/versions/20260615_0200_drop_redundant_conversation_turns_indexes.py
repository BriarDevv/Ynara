"""drop indices redundantes de conversation_turns (auditoria backend).

Tabla OPERATIVA (no sagrada, regla #3). El UNIQUE ``(session_id, seq)``
(``uq_conversation_turns_session_id_seq``) ya crea un indice B-tree implicito
sobre ``(session_id, seq)``, asi que dos indices de la migracion original quedan
redundantes y solo agregan overhead de escritura en cada INSERT:

- ``ix_conversation_turns_session_id_seq`` (non-unique, ``(session_id, seq)``):
  duplica exacto el indice implicito del UNIQUE.
- ``ix_conversation_turns_session_id`` (non-unique, ``(session_id,)``): cubierto
  por el prefijo izquierdo del indice compuesto del UNIQUE.

Se mantiene ``ix_conversation_turns_user_id`` (columna distinta, lo usan las
queries por usuario). El downgrade recrea ambos para round-trip limpio.

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
    # Ambos redundantes con el indice implicito del UNIQUE(session_id, seq).
    op.drop_index("ix_conversation_turns_session_id_seq", table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_session_id"), table_name="conversation_turns")


def downgrade() -> None:
    # Recrea los indices tal cual los creaba la migracion original (round-trip).
    op.create_index(
        op.f("ix_conversation_turns_session_id"),
        "conversation_turns",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_turns_session_id_seq",
        "conversation_turns",
        ["session_id", "seq"],
        unique=False,
    )
