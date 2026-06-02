"""Schemas Pydantic v2 de request/response.

Convención: un archivo por dominio. La fuente de verdad de los
contratos vive acá; ``packages/shared-schemas/`` (Zod) replica a mano.
"""

from app.schemas.audit import AuditLogOut
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenOut
from app.schemas.base import YnaraBaseModel
from app.schemas.chat import Action, ChatHttpRequest, ChatHttpResponse
from app.schemas.memory import (
    EpisodicMemoryCreate,
    EpisodicMemoryOut,
    MemorySettingsUpdate,
    ProceduralMemoryOut,
    ProceduralMemoryUpsert,
    SemanticMemoryCreate,
    SemanticMemoryOut,
    SemanticMemoryUpdate,
)
from app.schemas.memory_api import (
    EpisodicMemoryPage,
    MemoryExport,
    MemoryGroupedResponse,
    MemoryPatchRequest,
    MemoryWipeConfirm,
    MemoryWipePreview,
    MemoryWipeResult,
    ProceduralMemoryPage,
    SemanticMemoryPage,
)
from app.schemas.session import SessionClose, SessionCreate, SessionOut
from app.schemas.session_api import SessionListPage
from app.schemas.user import UserBase, UserCreate, UserOut, UserUpdate

__all__ = [
    "Action",
    "AuditLogOut",
    "ChatHttpRequest",
    "ChatHttpResponse",
    "EpisodicMemoryCreate",
    "EpisodicMemoryOut",
    "EpisodicMemoryPage",
    "LoginRequest",
    "LogoutRequest",
    "MemoryExport",
    "MemoryGroupedResponse",
    "MemoryPatchRequest",
    "MemorySettingsUpdate",
    "MemoryWipeConfirm",
    "MemoryWipePreview",
    "MemoryWipeResult",
    "ProceduralMemoryOut",
    "ProceduralMemoryPage",
    "ProceduralMemoryUpsert",
    "RefreshRequest",
    "RegisterRequest",
    "SemanticMemoryCreate",
    "SemanticMemoryOut",
    "SemanticMemoryPage",
    "SemanticMemoryUpdate",
    "SessionClose",
    "SessionCreate",
    "SessionListPage",
    "SessionOut",
    "TokenOut",
    "UserBase",
    "UserCreate",
    "UserOut",
    "UserUpdate",
    "YnaraBaseModel",
]
