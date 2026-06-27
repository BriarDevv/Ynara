"""Modelos SQLAlchemy de Ynara.

Cualquier modelo nuevo se documenta en ``apps/backend/docs/MODELS.md``.
Tablas sagradas (memoria) tienen reglas especiales: ver
``apps/backend/AGENTS.md`` y regla #3 de ``AGENTS.md`` raíz.
"""

from app.models.admin_audit import AdminAudit
from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.calendar_event import CalendarEvent
from app.models.conversation_turn import ConversationTurn
from app.models.device_token import DeviceToken
from app.models.memory import (
    EpisodicMemory,
    ProceduralMemory,
    SemanticMemory,
)
from app.models.reminder import Reminder
from app.models.session import ChatSession
from app.models.task import Task
from app.models.user import User

__all__ = [
    "AdminAudit",
    "AuditLog",
    "Base",
    "CalendarEvent",
    "ChatSession",
    "ConversationTurn",
    "DeviceToken",
    "EpisodicMemory",
    "ProceduralMemory",
    "Reminder",
    "SemanticMemory",
    "Task",
    "TimestampMixin",
    "UUIDPKMixin",
    "User",
]
