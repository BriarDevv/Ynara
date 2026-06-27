"""add time_zone to users.

GATE (regla #3 + CLAUDE.md): toca ``users`` (tabla SENSIBLE, no sagrada) agregando
``time_zone`` con ``server_default='UTC'`` para no romper filas existentes (mismo patrón
que ``is_admin``: default seguro, SIN backfill). Es ``String(64)`` NOT NULL. El downgrade
es simétrico y NO destruye datos de otras tablas: dropea solo la columna ``time_zone``.

Revision ID: a7b1c2d3e4f5
Revises: c1d2e3f4a5b6
Create Date: 2026-06-25 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b1c2d3e4f5"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users.time_zone — tabla SENSIBLE. server_default='UTC': las filas existentes quedan
    # en UTC sin necesitar backfill. El server_default se mantiene en DB (idempotente para
    # inserts crudos / data-migrations futuras), igual que is_admin.
    op.add_column(
        "users",
        sa.Column(
            "time_zone",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'UTC'"),
        ),
    )


def downgrade() -> None:
    # Simétrico: dropea SOLO la columna que esta migración creó. No toca otras tablas/datos.
    op.drop_column("users", "time_zone")
