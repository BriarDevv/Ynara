"""Modelos SQLAlchemy de Ynara.

Cualquier modelo nuevo se documenta en ``apps/backend/docs/MODELS.md``.
Tablas sagradas (memoria) tienen reglas especiales: ver
``apps/backend/AGENTS.md`` y regla #3 de ``AGENTS.md`` raíz.
"""

from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.conversation_turn import ConversationTurn
from app.models.memory import (
    EMBEDDING_DIM,
    EpisodicMemory,
    ProceduralMemory,
    SemanticMemory,
)
from app.models.session import ChatSession
from app.models.user import User

__all__ = [
    "EMBEDDING_DIM",
    "AuditLog",
    "Base",
    "ChatSession",
    "ConversationTurn",
    "EpisodicMemory",
    "ProceduralMemory",
    "SemanticMemory",
    "TimestampMixin",
    "UUIDPKMixin",
    "User",
]
