"""Modelo SQLAlchemy de evento de agenda: ``calendar_events``.

Tabla **OPERATIVA**, no sagrada (regla #3): el dominio Agenda (ADR-018) lo
consume web + mobile vía ``/v1/events``. Es el modelo canónico iCalendar/RFC 5545
aterrizado al stack: ``start_at`` (instante con offset) + ``duration_min`` (el fin
es derivado), más ``time_zone`` / ``all_day`` / ``recurrence`` para soportar huso
real, día completo y recurrencia. El shape espeja
``packages/shared-schemas/src/agenda.ts`` ("Pydantic gana, Zod sigue").

Invariante ADR-018: un evento con ``recurrence`` no vacía DEBE traer
``time_zone`` (si no el recurrente se corre en los cambios de DST). La invariante
se enforcea en los schemas Pydantic (``app/schemas/calendar_event.py``), no acá:
el modelo solo declara columnas. La expansión de recurrencia es client-side
(``@ynara/core``); el backend guarda ``recurrence`` como array de texto y devuelve
los eventos tal cual están almacenados (no expande server-side, fase posterior).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import EventStatus, Mode, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


__all__ = ["CalendarEvent"]


class CalendarEvent(UUIDPKMixin, TimestampMixin, Base):
    """Un evento de agenda de un usuario.

    Un usuario tiene N eventos. ``start_at`` + ``duration_min`` arman el bloque
    (el fin es derivado); ``mode`` lo tinta (``None`` si es transversal);
    ``status`` arranca ``confirmed``. Los campos de calendario v2 (``time_zone`` /
    ``all_day`` / ``recurrence``, ADR-018) son nullable/con default para
    back-compat con el contrato del front.
    """

    __tablename__ = "calendar_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    # mode_enum ya existe (dueño: ``ChatSession.mode``): create_type=False evita el
    # doble-create en Alembic (mismo patrón que ``AuditLog.origin_mode``).
    mode: Mapped[Mode | None] = mapped_column(
        Enum(
            Mode,
            name="mode_enum",
            native_enum=True,
            values_callable=enum_values,
            create_type=False,
        ),
        nullable=True,
    )
    # event_status_enum es propio de esta tabla; la migración lo crea explícitamente
    # (como turn_role_enum), así que la columna pasa create_type=False.
    status: Mapped[EventStatus] = mapped_column(
        Enum(
            EventStatus,
            name="event_status_enum",
            native_enum=True,
            values_callable=enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    recurrence: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    user: Mapped[User] = relationship(back_populates="events")
