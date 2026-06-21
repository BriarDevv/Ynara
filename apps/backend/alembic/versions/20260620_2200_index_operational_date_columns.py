"""index sessions.started_at and users.created_at

Tablas OPERATIVAS (no sagradas): ``sessions`` y ``users``. El panel admin filtra y
agrupa por estas columnas de fecha en casi todos sus endpoints (overview, heatmap de
~53 semanas, active-users, modes mix, signups), lo que sin indice provoca sequential
scans crecientes por request. Indices btree ADITIVOS; downgrade simetrico (dropea solo
lo que crea, no toca datos ni otras tablas). NO toca tablas sagradas (regla #3).

Revision ID: d1c2b3a49e87
Revises: f3a9c1d27e84
Create Date: 2026-06-20 22:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1c2b3a49e87"
down_revision: str | None = "f3a9c1d27e84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nombres via op.f(...) = literal segun NAMING_CONVENTION (ix_<table>_<col>),
    # coherentes con el index=True del modelo (sessions) y el Index(...) explicito (users).
    op.create_index(op.f("ix_sessions_started_at"), "sessions", ["started_at"], unique=False)
    op.create_index(op.f("ix_users_created_at"), "users", ["created_at"], unique=False)


def downgrade() -> None:
    # Simetrico: dropea SOLO los indices que esta migracion creo.
    op.drop_index(op.f("ix_users_created_at"), table_name="users")
    op.drop_index(op.f("ix_sessions_started_at"), table_name="sessions")
