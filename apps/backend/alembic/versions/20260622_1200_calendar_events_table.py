"""calendar_events - tabla operativa del dominio Agenda (ADR-023).

Tabla OPERATIVA (no sagrada, regla #3): eventos de agenda del usuario, que web +
mobile consumen vía ``/v1/events``. Modelo canónico iCalendar/RFC 5545 aterrizado
al stack: ``start_at`` (instante con offset) + ``duration_min`` (fin derivado), más
``time_zone`` / ``all_day`` / ``recurrence`` (huso real, día completo, recurrencia).

Crea el tipo enum nativo ``event_status_enum`` (dueño: ``CalendarEvent.status``) +
la tabla ``calendar_events`` con FK a ``users`` (``ON DELETE CASCADE``), el PK y
los índices en ``user_id`` y ``start_at`` (el front filtra/ordena por inicio). NO
toca ``mode_enum`` (ya existe; ``mode`` lo reusa con ``create_type=False``). El
downgrade dropea índices + tabla + el enum (round-trip limpio).

Revision ID: e5d9f2a73c1b
Revises: d1c2b3a49e87
Create Date: 2026-06-22 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5d9f2a73c1b"
down_revision: str | None = "d1c2b3a49e87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tipo enum nativo creado explicitamente; create_type=False en la columna
    # evita el doble-create (mismo patron que turn_role_enum en la migracion de
    # conversation_turns). event_status_enum es propio de calendar_events.
    bind = op.get_bind()
    postgresql.ENUM(
        "confirmed",
        "tentative",
        "cancelled",
        name="event_status_enum",
        create_type=False,
    ).create(bind, checkfirst=True)

    op.create_table(
        "calendar_events",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        # mode_enum ya existe (dueño: sessions.mode): create_type=False, no se re-crea.
        sa.Column(
            "mode",
            postgresql.ENUM(
                "productividad",
                "estudio",
                "bienestar",
                "vida",
                "memoria",
                name="mode_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "confirmed",
                "tentative",
                "cancelled",
                name="event_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("time_zone", sa.String(), nullable=True),
        sa.Column(
            "all_day",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("recurrence", postgresql.ARRAY(sa.String()), nullable=True),
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
            name=op.f("fk_calendar_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_events")),
    )
    op.create_index(
        op.f("ix_calendar_events_user_id"),
        "calendar_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calendar_events_start_at"),
        "calendar_events",
        ["start_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_events_start_at"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_user_id"), table_name="calendar_events")
    op.drop_table("calendar_events")
    op.execute("DROP TYPE IF EXISTS event_status_enum")
