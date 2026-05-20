"""Modelo SQLAlchemy de audit log de operaciones sobre memoria.

Toda operación read/write/update/delete sobre las 3 capas queda
registrada. Retention: 24 meses (MEMORY.md). Worker periódico borra
entradas más viejas. ``sensitive=true`` para operaciones sobre entradas
``is_sensitive=true`` de memoria episódica — permite queries
diferenciadas y exports separados.

No usa ``TimestampMixin``: una vez creada, una entrada de audit no se
modifica (solo ``created_at``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.base import Base, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(UUIDPKMixin, Base):
    """Registro inmutable de una operación sobre memoria."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="record_hash_sha256_hex",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[AuditOperation] = mapped_column(
        Enum(AuditOperation, name="audit_operation_enum", native_enum=True),
        nullable=False,
    )
    target_layer: Mapped[MemoryLayer] = mapped_column(
        Enum(MemoryLayer, name="memory_layer_enum", native_enum=True),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    origin_model: Mapped[LlmModel | None] = mapped_column(
        Enum(LlmModel, name="llm_model_enum", native_enum=True),
        nullable=True,
    )
    origin_mode: Mapped[Mode | None] = mapped_column(
        Enum(Mode, name="mode_enum", native_enum=True, create_type=False),
        nullable=True,
    )
    origin_tool: Mapped[str | None] = mapped_column(String(80), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="audit_logs")
