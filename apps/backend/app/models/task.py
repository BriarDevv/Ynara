"""Modelo SQLAlchemy de tarea/prioridad del día: ``tasks``.

Tabla **OPERATIVA**, no sagrada (regla #3): el dominio TAREAS (Fase D1, espejo de
Agenda/ADR-023) lo consume el dashboard "Hoy" de la web vía ``/v1/tasks``. Destraba
el front mock-first de prioridades: el agente qwen extrae to-dos de lo conversado
(igual que agenda eventos) y la pantalla los lista/togglea. El shape espeja
``packages/shared-schemas/src/today.ts`` (``TaskSchema``: "Pydantic gana, Zod sigue").

A diferencia de ``CalendarEvent`` (donde ``start_at`` / ``duration_min`` son NOT
NULL — un evento siempre tiene inicio y duración), una ``Task`` puede no tener
horario: ``scheduled_at`` y ``duration_min`` son **NULLABLE** (el front los declara
``.nullable()``). El fin del bloque (cuando hay horario) es derivado
(``scheduled_at + duration_min``), no un campo.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import TaskStatus, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


__all__ = ["Task"]


class Task(UUIDPKMixin, TimestampMixin, Base):
    """Una tarea/prioridad del día de un usuario.

    Un usuario tiene N tareas. ``title`` la describe; ``status`` arranca
    ``pending`` y el front lo togglea a ``done`` (el check). ``scheduled_at`` +
    ``duration_min`` (ambos NULLABLE) arman la meta "14:00 · 45 min" cuando la
    tarea tiene horario; ``null`` si es una prioridad sin hora fija.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        # El listado del dashboard "Hoy" (``GET /v1/tasks`` / ``TaskStore.list_tasks``)
        # filtra por ``user_id`` y ordena por ``scheduled_at`` ASC. Índice btree compuesto
        # ``(user_id, scheduled_at)`` (ALB-04): acota el scan a las filas del user y sirve
        # el orden por horario sin sort. ``user_id`` solo (FK, ``index=True`` abajo) queda
        # para el CASCADE y lookups simples.
        Index("ix_tasks_user_id_scheduled_at", "user_id", "scheduled_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    # task_status_enum es propio de esta tabla; la migración lo crea explícitamente
    # (como event_status_enum), así que la columna pasa create_type=False.
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status_enum",
            native_enum=True,
            values_callable=enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    # NULLABLE (a diferencia de CalendarEvent.start_at): una prioridad puede no
    # tener horario fijo. El front lo declara ``.nullable()``.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship(back_populates="tasks")
