"""device_tokens - tabla operativa de tokens de push (PR-B).

Tabla OPERATIVA (no sagrada, regla #3): device tokens (FCM/APNS/web push) de los
dispositivos del usuario. El scheduler de recordatorios los carga para despachar avisos
vía el ``NotificationDelivery`` (hoy un noop).

Crea el tipo enum nativo ``device_platform_enum`` (dueño: ``DeviceToken.platform``) + la
tabla ``device_tokens`` con FK a ``users`` (``ON DELETE CASCADE``), el PK, el índice en
``user_id`` y el UNIQUE sobre ``token`` (un dispositivo no se duplica; un re-registro
re-asigna el dueño). NO toca ningún enum existente. El downgrade dropea índice/unique +
tabla + el enum (round-trip limpio, simétrico).

Revision ID: b2c3d4e5f6a7
Revises: a7b1c2d3e4f5
Create Date: 2026-06-25 11:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a7b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipo enum nativo creado explicitamente; create_type=False en la columna evita el
    # doble-create (mismo patron que task_status_enum). device_platform_enum es propio de
    # device_tokens.
    bind = op.get_bind()
    postgresql.ENUM(
        "ios",
        "android",
        "web",
        name="device_platform_enum",
        create_type=False,
    ).create(bind, checkfirst=True)

    op.create_table(
        "device_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM(
                "ios",
                "android",
                "web",
                name="device_platform_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
            name=op.f("fk_device_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_tokens")),
        sa.UniqueConstraint("token", name=op.f("uq_device_tokens_token")),
    )
    op.create_index(
        op.f("ix_device_tokens_user_id"),
        "device_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_table("device_tokens")
    op.execute("DROP TYPE IF EXISTS device_platform_enum")
