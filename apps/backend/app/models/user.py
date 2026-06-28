"""Modelo SQLAlchemy de usuario.

Los helpers de auth (hashing + JWT) viven en ``app/core/security.py`` (ya
implementados). El módulo ``/v1/auth`` (``app/api/v1/auth.py`` +
``app/services/auth.py``) conecta ``password_hash``: ``register`` lo puebla con
el hash bcrypt y ``token`` lo verifica. ``password_hash`` sigue siendo
``nullable`` porque los usuarios efímeros no tienen credenciales.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.admin_audit import AdminAudit
    from app.models.audit import AuditLog
    from app.models.calendar_event import CalendarEvent
    from app.models.device_token import DeviceToken
    from app.models.memory import EpisodicMemory, ProceduralMemory, SemanticMemory
    from app.models.reminder import Reminder
    from app.models.session import ChatSession
    from app.models.task import Task


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
        # created_at viene del TimestampMixin (compartido con tablas SAGRADAS): el
        # índice se declara acá, a nivel User, para NO indexar created_at en las 3
        # capas de memoria (eso requeriría gate regla #3). El panel admin filtra/agrupa
        # por users.created_at (signups, growth) — sin índice son full scans a escala.
        Index("ix_users_created_at", "created_at"),
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
    # Huso horario IANA del usuario (p.ej. ``America/Argentina/Buenos_Aires``). Mismo
    # criterio que ``is_admin``: ``server_default='UTC'`` para no romper filas existentes
    # en la migración (tabla sensible — sin backfill, default seguro). Se llama
    # ``time_zone`` (no ``timezone``) por consistencia con ``calendar_events.time_zone``.
    # La validación IANA vive en el boundary Pydantic (``validate_iana_tz``), no acá: el
    # modelo solo declara la columna.
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'UTC'"))
    # Prefs OPERATIVAS del onboarding (modos de interés + a11y): "cómo configuro la app para
    # este usuario", NO "quién es" (eso es memoria sagrada — ADR-026, sembrada en G4 aparte).
    # JSONB en vez de N columnas: la forma la fija el contrato Pydantic (``UserPreferences``),
    # no el schema SQL. ``server_default='{}'::jsonb`` para no romper filas existentes en la
    # migración (tabla sensible, sin backfill); las filas viejas quedan con ``{}``.
    preferences: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    retention_sensitive_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)

    sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    events: Mapped[list[CalendarEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="user", cascade="all, delete-orphan")
    device_tokens: Mapped[list[DeviceToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reminders: Mapped[list[Reminder]] = relationship(
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
