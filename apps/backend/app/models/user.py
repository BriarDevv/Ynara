"""Modelo SQLAlchemy de usuario.

Auth completa vive en ``app/core/security.py`` (todavía
``NotImplementedError``). Este modelo expone los campos que la API y la
memoria necesitan; ``password_hash`` queda placeholder hasta que el PR de
auth lo conecte.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
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
