"""Modelos SQLAlchemy de las 3 capas de memoria. TABLAS SAGRADAS.

Cualquier cambio acá requiere tests + 1 aprobación humana explícita
(regla #3 de ``AGENTS.md``). Schema definido en ADR-007 (decay, retention
diferenciada, encriptación a nivel campo).

- ``SemanticMemory``: hechos persistentes sobre el usuario. ``content``
  cifrado AES-256-GCM (BYTEA) vía ``app/core/crypto.py`` (PR C).
- ``EpisodicMemory``: resúmenes de sesiones. ``summary`` cifrado.
  ``is_sensitive`` se setea True automáticamente cuando la sesión cierra
  en modo Bienestar; el worker de retention respeta
  ``retention_days``.
- ``ProceduralMemory``: preferencias del usuario. ``value`` queda JSONB
  plain (no sensible). Decay exponencial sobre ``confidence``; ``stale``
  marca cuando ``confidence < 0.3``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EMBEDDING_DIM
from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.session import ChatSession
    from app.models.user import User


# ``EMBEDDING_DIM`` (bge-m3, 1024) es la fuente única de verdad de
# ``app/core/constants.py``. Se importa acá para ``Vector(EMBEDDING_DIM)`` y
# queda re-exportado por el namespace del módulo: ``from app.models.memory
# import EMBEDDING_DIM`` sigue funcionando.


class SemanticMemory(UUIDPKMixin, TimestampMixin, Base):
    """Hecho persistente sobre el usuario. Solo Qwen escribe acá."""

    __tablename__ = "semantic_memory"
    __table_args__ = (
        CheckConstraint(
            "importance IS NULL OR (importance BETWEEN 0 AND 100)",
            name="importance_range",
        ),
        Index(
            "ix_semantic_memory_content_embedding_hnsw",
            "content_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"content_embedding": "vector_cosine_ops"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    importance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="semantic_memories")


class EpisodicMemory(UUIDPKMixin, TimestampMixin, Base):
    """Resumen de una sesión. Se genera via Celery al cerrarse la sesión.

    ``is_sensitive=true`` se setea para sesiones en modo Bienestar, y
    gatilla retention más corto (``user.retention_sensitive_days``) + audit
    log diferenciado + export separado.
    """

    __tablename__ = "episodic_memory"
    __table_args__ = (
        CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="retention_days_range",
        ),
        CheckConstraint(
            "(is_sensitive = false) OR (retention_days BETWEEN 1 AND 365)",
            name="retention_days_sensitive_cap",
        ),
        Index(
            "ix_episodic_memory_summary_embedding_hnsw",
            "summary_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"summary_embedding": "vector_cosine_ops"},
        ),
        # Lista de episódica reciente del panel admin (ORDER BY occurred_at DESC sin
        # filtro de user_id): un btree sobre occurred_at evita el seq-scan + sort
        # (migración 20260623_1200). El btree ascendente sirve el DESC por backward scan.
        Index("ix_episodic_memory_occurred_at", "occurred_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    summary_embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    topics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    user: Mapped[User] = relationship(back_populates="episodic_memories")
    session: Mapped[ChatSession] = relationship(back_populates="episodic_memory")


class ProceduralMemory(UUIDPKMixin, TimestampMixin, Base):
    """Preferencia o patrón del usuario. Decay exponencial sobre
    ``confidence``: worker Celery diario aplica ``confidence *= 0.9``
    cuando pasaron ``ynara.config.json[memory].decay_interval_days``
    desde ``last_reinforced_at``. Cuando ``confidence < 0.3`` queda
    ``stale=true``. Ver ADR-007 D1.
    """

    __tablename__ = "procedural_memory"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="user_id_key_unique"),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="confidence_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_reinforced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="procedural_memories")
