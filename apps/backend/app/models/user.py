"""Modelo SQLAlchemy de usuario.

Los helpers de auth (hashing + JWT) viven en ``app/core/security.py`` (ya
implementados). El módulo ``/v1/auth`` (``app/api/v1/auth.py`` +
``app/services/auth.py``) conecta ``password_hash``: ``register`` lo puebla con
el hash bcrypt y ``token`` lo verifica. ``password_hash`` sigue siendo
``nullable`` porque los usuarios efímeros no tienen credenciales.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.admin_audit import AdminAudit
    from app.models.audit import AuditLog
    from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
    from app.models.session import ChatSession


class User(UUIDPKMixin, TimestampMixin, Base):
    """Usuario de Ynara.

    Campos de retention: ``retention_sensitive_days`` configura el TTL
    de memoria episódica marcada ``is_sensitive=true`` (modo Bienestar
    por defecto). Rango 30-365, default 180. Ver ADR-007.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "retention_sensitive_days BETWEEN 30 AND 365",
            name="retention_sensitive_days_range",
        ),
    )

    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Flag de admin del panel interno (/v1/admin/*). ``server_default=false`` para no
    # romper filas existentes en la migración (tabla SAGRADA, gate humano). El bootstrap
    # inicial (antes de poblar esta columna) se cubre con ``ADMIN_BOOTSTRAP_IDS`` en
    # ``get_current_admin``; esta flag es la fuente de verdad persistente.
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    retention_sensitive_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)

    sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    semantic_memories: Mapped[list[SemanticMemory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    episodic_memories: Mapped[list[EpisodicMemory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    procedural_memories: Mapped[list[ProceduralMemory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    admin_audits: Mapped[list[AdminAudit]] = relationship(
        back_populates="admin", cascade="all, delete-orphan"
    )
