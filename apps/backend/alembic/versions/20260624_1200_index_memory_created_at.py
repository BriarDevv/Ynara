"""index created_at en las 3 capas de memoria (panel admin growth/moat)

Tablas SAGRADAS: ``semantic_memory`` / ``episodic_memory`` / ``procedural_memory``
(regla #3 de ``AGENTS.md`` — tests + 1 aprobación humana explícita en el PR). Las
métricas de crecimiento/moat del panel admin (``app/services/admin_metrics.py``) corren
``COUNT(*) WHERE created_at < start`` y ``date_trunc('day', created_at)`` CROSS-USER
(sin filtro de ``user_id``) sobre las tres capas. Sin índice → sequential scan + sort de
toda la tabla por request, que crece con los datos. Índices btree ADITIVOS sobre
``created_at`` (mismo criterio que ``ix_users_created_at`` / ``ix_sessions_started_at``
en 20260620 y ``ix_episodic_memory_occurred_at`` en 20260623). NO destruyen datos;
downgrade simétrico (dropea SOLO lo que crea, en orden inverso, sin tocar datos ni otras
tablas / índices).

Revision ID: b8e4f2a1c3d6
Revises: e5f1a2b3c4d6
Create Date: 2026-06-24 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4f2a1c3d6"
down_revision: str | None = "e5f1a2b3c4d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ix_<table>_<col> via op.f(...), coherente con el Index(...) explícito de cada modelo.
    op.create_index(
        op.f("ix_semantic_memory_created_at"),
        "semantic_memory",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_episodic_memory_created_at"),
        "episodic_memory",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_procedural_memory_created_at"),
        "procedural_memory",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Simétrico: dropea SOLO los índices que esta migración creó, en orden inverso.
    op.drop_index(op.f("ix_procedural_memory_created_at"), table_name="procedural_memory")
    op.drop_index(op.f("ix_episodic_memory_created_at"), table_name="episodic_memory")
    op.drop_index(op.f("ix_semantic_memory_created_at"), table_name="semantic_memory")
