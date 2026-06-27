"""reminders - tabla operativa de recordatorios (PR-C).

Tabla OPERATIVA (no sagrada, regla #3): recordatorios del usuario que el tool
``reminder.set`` / ``reminder.list`` crea/lista y que el scheduler
(``app/workflows/reminder_dispatch.py``) despacha cuando vencen.

Crea el tipo enum nativo ``reminder_status_enum`` (dueño: ``Reminder.status``) + la tabla
``reminders`` con FK a ``users`` (``ON DELETE CASCADE``), el PK, el índice en ``user_id``
y DOS índices compuestos: ``(user_id, remind_at)`` (listado por-usuario) y ``(status,
remind_at)`` (scan GLOBAL del scheduler ``WHERE status='pending' AND remind_at<=now``).
NO toca ningún enum existente. El downgrade dropea índices + tabla + el enum (round-trip
limpio, simétrico).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipo enum nativo creado explicitamente; create_type=False en la columna evita el
    # doble-create (mismo patron que task_status_enum). reminder_status_enum es propio de
    # reminders.
    bind = op.get_bind()
    postgresql.ENUM(
        "pending",
        "sent",
        "cancelled",
        name="reminder_status_enum",
        create_type=False,
    ).create(bind, checkfirst=True)

    op.create_table(
        "reminders",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "sent",
                "cancelled",
                name="reminder_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reminders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminders")),
    )
    op.create_index(
        op.f("ix_reminders_user_id"),
        "reminders",
        ["user_id"],
        unique=False,
    )
    # Compuesto del listado por-usuario (user_id + orden/filtro por remind_at).
    op.create_index(
        op.f("ix_reminders_user_id_remind_at"),
        "reminders",
        ["user_id", "remind_at"],
        unique=False,
    )
    # Compuesto del scan GLOBAL del scheduler (status='pending' AND remind_at<=now).
    op.create_index(
        op.f("ix_reminders_status_remind_at"),
        "reminders",
        ["status", "remind_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reminders_status_remind_at"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_user_id_remind_at"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_user_id"), table_name="reminders")
    op.drop_table("reminders")
    op.execute("DROP TYPE IF EXISTS reminder_status_enum")
