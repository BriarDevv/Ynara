"""index tasks (user_id, scheduled_at) — listado del dashboard Hoy

Tabla OPERATIVA (no sagrada): ``tasks`` (dominio TAREAS). El listado del dashboard
"Hoy" (``GET /v1/tasks`` / ``TaskStore.list_tasks``) filtra por ``user_id`` y ordena por
``scheduled_at`` ASC. Sin un índice que combine ambos, el filtro usa ``ix_tasks_user_id``
(solo) y el orden se resuelve con un sort por request. Índice btree compuesto ADITIVO
``(user_id, scheduled_at)`` (ALB-04): acota el scan a las filas del user y sirve el orden
por horario sin sort. NO destruye datos ni toca el ``ix_tasks_user_id`` existente (FK +
lookups simples). Downgrade simétrico (dropea solo lo que crea).

Revision ID: c1d2e3f4a5b6
Revises: b8e4f2a1c3d6
Create Date: 2026-06-24 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b8e4f2a1c3d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ix_<table>_<cols> via op.f(...), coherente con el Index(...) explícito del modelo.
    op.create_index(
        op.f("ix_tasks_user_id_scheduled_at"),
        "tasks",
        ["user_id", "scheduled_at"],
        unique=False,
    )


def downgrade() -> None:
    # Simétrico: dropea SOLO el índice que esta migración creó.
    op.drop_index(op.f("ix_tasks_user_id_scheduled_at"), table_name="tasks")
