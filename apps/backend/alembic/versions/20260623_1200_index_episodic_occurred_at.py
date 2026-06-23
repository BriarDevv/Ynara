"""index episodic_memory.occurred_at

Tabla SAGRADA: ``episodic_memory`` (regla #3 de ``AGENTS.md`` — tests + 1 aprobación
humana explícita en el PR). El panel admin lista la episódica reciente con
``ORDER BY occurred_at DESC LIMIT N`` (``app/services/admin_metrics.py``, recent_episodic)
SIN filtro de ``user_id``, lo que sin índice provoca un sequential scan + sort de toda la
tabla por request. Índice btree ADITIVO sobre ``occurred_at``: un btree ascendente sirve
el ``ORDER BY ... DESC`` vía backward scan (mismo criterio que ``ix_sessions_started_at``
en 20260620). NO destruye datos; downgrade simétrico (dropea solo lo que crea, no toca
datos ni otras tablas).

Revision ID: e5f1a2b3c4d6
Revises: c3dcbf9ab7d9
Create Date: 2026-06-23 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f1a2b3c4d6"
down_revision: str | None = "c3dcbf9ab7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ix_<table>_<col> via op.f(...), coherente con el Index(...) explícito del modelo.
    op.create_index(
        op.f("ix_episodic_memory_occurred_at"),
        "episodic_memory",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    # Simétrico: dropea SOLO el índice que esta migración creó.
    op.drop_index(op.f("ix_episodic_memory_occurred_at"), table_name="episodic_memory")
