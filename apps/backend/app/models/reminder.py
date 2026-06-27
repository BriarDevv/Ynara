"""Modelo SQLAlchemy de recordatorio: ``reminders``.

Tabla **OPERATIVA**, no sagrada (regla #3): recordatorios del usuario que el tool
``reminder.set`` / ``reminder.list`` (``app/llm/tools/reminder.py``) crea/lista y que
el scheduler (``app/workflows/reminder_dispatch.py``) despacha cuando vencen. Tabla
DEDICADA (NO se reusan ``tasks``): un recordatorio es un aviso por-tiempo (``remind_at``
+ ``status``), no una prioridad del día.

``text`` (no ``title``, a diferencia de ``Task``) mapea el ``text`` del contrato de la
tool; ``remind_at`` mapea el ``when``. ``status`` arranca ``pending`` y el scheduler lo
pasa a ``sent`` al despachar (o el usuario a ``cancelled``).

Privacidad (regla #4): ``text`` es contenido del usuario, NO se loguea (ni el scheduler
ni el notifier lo emiten a logs).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ReminderStatus, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


__all__ = ["Reminder"]


class Reminder(UUIDPKMixin, TimestampMixin, Base):
    """Un recordatorio de un usuario.

    Un usuario tiene N recordatorios. ``text`` lo describe; ``remind_at`` es cuándo
    avisar (instante con offset); ``status`` arranca ``pending``, pasa a ``sent`` cuando
    el scheduler despacha el aviso, o a ``cancelled`` si el usuario lo cancela.
    """

    __tablename__ = "reminders"
    __table_args__ = (
        # El listado por-usuario del tool ``reminder.list`` y del CRUD filtra por
        # ``user_id`` y ordena/filtra por ``remind_at``: el compuesto ``(user_id,
        # remind_at)`` acota el scan al user y sirve el orden sin sort. ``user_id`` solo
        # (FK, ``index=True`` abajo) queda para el CASCADE y lookups simples.
        Index("ix_reminders_user_id_remind_at", "user_id", "remind_at"),
        # El scan GLOBAL del scheduler (``reminder_dispatch``) es
        # ``WHERE status='pending' AND remind_at <= now ORDER BY remind_at`` SIN filtro de
        # ``user_id`` (por-tiempo, cross-user): este compuesto ``(status, remind_at)`` lo
        # sirve sin seq-scan + sort de toda la tabla.
        Index("ix_reminders_status_remind_at", "status", "remind_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 1000 chars: cota compartida con el schema REST (``_Text`` en
    # ``app/schemas/reminder.py``). La tool del agente capa aparte en 200.
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # reminder_status_enum es propio de esta tabla; la migración lo crea explícitamente
    # (como task_status_enum), así que la columna pasa create_type=False.
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(
            ReminderStatus,
            name="reminder_status_enum",
            native_enum=True,
            values_callable=enum_values,
            create_type=False,
        ),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="reminders")
