"""add is_admin to users + admin_audit table.

GATE (regla #3 + CLAUDE.md): toca ``users`` (tabla SAGRADA) agregando ``is_admin``
con ``server_default=false`` para no romper filas existentes. Crea ademas la tabla
OPERATIVA ``admin_audit`` (audit de acciones del operador del panel /v1/admin/*; NO
es ``audit_log``, que es sagrada e inmutable). El downgrade es simetrico y NO destruye
datos de otras tablas: dropea solo la columna ``is_admin`` y la tabla ``admin_audit``.

Revision ID: f3a9c1d27e84
Revises: b7e2f4a16c9d
Create Date: 2026-06-19 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d27e84"
down_revision: str | None = "b7e2f4a16c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (a) users.is_admin — tabla SAGRADA. server_default=false: las filas existentes
    # quedan no-admin sin necesitar backfill (el bootstrap inicial se cubre con
    # ADMIN_BOOTSTRAP_IDS en get_current_admin). El server_default se mantiene en DB
    # (idempotente para inserts crudos / data-migrations futuras).
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # (b) admin_audit — tabla operativa (UUIDPKMixin + TimestampMixin). FK a users con
    # ON DELETE CASCADE (al borrar un admin se borra su rastro). naming via op.f(...)
    # (NAMING_CONVENTION de Base.metadata). meta es JSONB default '{}'.
    op.create_table(
        "admin_audit",
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            ["admin_id"],
            ["users.id"],
            name=op.f("fk_admin_audit_admin_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit")),
    )
    op.create_index(op.f("ix_admin_audit_admin_id"), "admin_audit", ["admin_id"], unique=False)


def downgrade() -> None:
    # Simetrico: dropea SOLO lo que esta migracion creo. No toca otras tablas/datos.
    op.drop_index(op.f("ix_admin_audit_admin_id"), table_name="admin_audit")
    op.drop_table("admin_audit")
    op.drop_column("users", "is_admin")
