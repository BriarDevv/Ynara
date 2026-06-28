"""add preferences (JSONB) to users.

GATE (regla #3 + CLAUDE.md): toca ``users`` (tabla SENSIBLE, no sagrada) agregando
``preferences`` JSONB con ``server_default='{}'::jsonb`` para no romper filas existentes
(mismo patrón que ``is_admin`` / ``time_zone``: default seguro, SIN backfill). Guarda las
prefs OPERATIVAS del onboarding (modos de interés + a11y), NO memoria sagrada (eso es G4,
PR aparte con aprobación). El downgrade es simétrico y NO destruye datos de otras tablas:
dropea solo la columna ``preferences``.

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-06-28 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users.preferences — tabla SENSIBLE. server_default='{}'::jsonb: las filas existentes
    # quedan con un objeto vacío sin necesitar backfill. El server_default se mantiene en DB
    # (idempotente para inserts crudos / data-migrations futuras), igual que is_admin/time_zone.
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    # Simétrico: dropea SOLO la columna que esta migración creó. No toca otras tablas/datos.
    op.drop_column("users", "preferences")
