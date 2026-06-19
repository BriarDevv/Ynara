"""Modelo SQLAlchemy de audit de acciones del panel admin interno.

Tabla OPERATIVA (no sagrada): registra las acciones que un admin ejecuta sobre el
panel interno (``/v1/admin/*``). NO es ``audit_log`` (que es sagrada, inmutable y
audita operaciones sobre la **memoria cifrada** del usuario): ``admin_audit`` audita
la actividad del **operador** del panel, no contenido del moat.

Privacidad (regla #4): ``admin_id`` es un UUID opaco (no PII); ``meta`` es JSONB para
contexto liviano de la acción (NUNCA contenido de memoria descifrado, NUNCA PII del
usuario observado). Se llama ``meta`` y no ``metadata`` porque ``metadata`` choca con
el atributo reservado de la declarative base de SQLAlchemy.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class AdminAudit(UUIDPKMixin, TimestampMixin, Base):
    """Registro de una acción del admin sobre el panel interno."""

    __tablename__ = "admin_audit"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    admin: Mapped[User] = relationship(back_populates="admin_audits")
