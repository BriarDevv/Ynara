"""tasks - tabla operativa del dominio TAREAS (Fase D1, espejo de Agenda/ADR-023).

Tabla OPERATIVA (no sagrada, regla #3): tareas/prioridades del día del usuario, que
el dashboard "Hoy" de la web consume vía ``/v1/tasks``. El alta la hace el agente
qwen por detrás de la conversación (``task.create_task``), igual que agenda eventos.
``scheduled_at`` + ``duration_min`` (ambos NULLABLE) arman la meta "14:00 · 45 min"
cuando la tarea tiene horario; el fin es derivado.

Crea el tipo enum nativo ``task_status_enum`` (dueño: ``Task.status``) + la tabla
``tasks`` con FK a ``users`` (``ON DELETE CASCADE``), el PK y el índice en
``user_id``. NO toca ningún enum existente. El downgrade dropea índice + tabla + el
enum (round-trip limpio, simétrico).

Revision ID: c3dcbf9ab7d9
Revises: e5d9f2a73c1b
Create Date: 2026-06-22 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3dcbf9ab7d9"
down_revision: str | None = "e5d9f2a73c1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipo enum nativo creado explicitamente; create_type=False en la columna evita
    # el doble-create (mismo patron que event_status_enum en la migracion de
    # calendar_events). task_status_enum es propio de tasks.
    bind = op.get_bind()
    postgresql.ENUM(
        "pending",
        "done",
        name="task_status_enum",
        create_type=False,
    ).create(bind, checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "done",
                name="task_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        # NULLABLE (a diferencia de calendar_events.start_at): una prioridad puede no
        # tener horario fijo (el front los declara nullable en today.ts).
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
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
            name=op.f("fk_tasks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(
        op.f("ix_tasks_user_id"),
        "tasks",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_table("tasks")
    op.execute("DROP TYPE IF EXISTS task_status_enum")
