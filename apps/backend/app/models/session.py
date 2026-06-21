"""Modelo SQLAlchemy de sesión de chat.

Una sesión es una conversación contigua de un usuario en un modo dado.
Al cerrarse (Qwen vía Celery), genera una entrada en ``episodic_memory``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Mode, enum_values
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.memory import EpisodicMemory
    from app.models.user import User


__all__ = ["ChatSession"]


class ChatSession(UUIDPKMixin, TimestampMixin, Base):
    """Sesión de chat. Un usuario puede tener N sesiones; cada sesión vive
    en un modo único (no se cambia de modo a mitad de la sesión: cerrar
    una y abrir otra).
    """

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[Mode] = mapped_column(
        Enum(Mode, name="mode_enum", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    episodic_memory: Mapped[EpisodicMemory | None] = relationship(
        back_populates="session", uselist=False
    )
