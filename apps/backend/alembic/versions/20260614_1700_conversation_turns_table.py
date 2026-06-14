"""conversation_turns - buffer transitorio de turnos crudos para la episodica.

Tabla OPERATIVA (no sagrada, regla #3): buffer de los turnos user/modelo de una
sesion que el worker episodico (``consolidate_session``) lee al cerrar la sesion
para resumir y persistir en ``episodic_memory`` (sagrada), y luego purga. El
``content`` viaja cifrado AES-256-GCM per-user (``BYTEA``), igual que la memoria
del moat (regla #4).

Crea el tipo enum nativo ``turn_role_enum`` (dueño: ``ConversationTurn.role``) +
la tabla ``conversation_turns`` con FKs a ``users`` y ``sessions``
(``ON DELETE CASCADE``), el UNIQUE ``(session_id, seq)`` y el indice compuesto
``(session_id, seq)``. El downgrade dropea la tabla y el enum (round-trip limpio).

Revision ID: c4e8a1d50b93
Revises: a1f3c9d27e84
Create Date: 2026-06-14 17:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1d50b93"
down_revision: str | None = "a1f3c9d27e84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipo enum nativo creado explicitamente; create_type=False en la columna
    # evita el doble-create (mismo patron que mode_enum/audit_operation_enum en
    # la migracion inicial). turn_role_enum es propio de conversation_turns.
    bind = op.get_bind()
    postgresql.ENUM("user", "model", name="turn_role_enum", create_type=False).create(
        bind, checkfirst=True
    )

    op.create_table(
        "conversation_turns",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("user", "model", name="turn_role_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_conversation_turns_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversation_turns_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_turns")),
        sa.UniqueConstraint("session_id", "seq", name="uq_conversation_turns_session_id_seq"),
    )
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


def downgrade() -> None:
    op.drop_index("ix_conversation_turns_session_id_seq", table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_user_id"), table_name="conversation_turns")
    op.drop_index(op.f("ix_conversation_turns_session_id"), table_name="conversation_turns")
    op.drop_table("conversation_turns")
    op.execute("DROP TYPE IF EXISTS turn_role_enum")
