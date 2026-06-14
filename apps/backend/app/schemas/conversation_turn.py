"""Schemas Pydantic para ``conversation_turns`` (tabla OPERATIVA).

Para el caller, ``content`` viaja en **plaintext** (lo cifra el store
``ConversationTurnStore`` antes de persistir; lo descifra al leer). En la DB vive
cifrado en ``BYTEA`` (AES-256-GCM per-user, regla #4). Mirror del modelo
``app/models/conversation_turn.py``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.enums import TurnRole
from app.schemas.base import YnaraBaseModel

# Tope defensivo del largo de un turno: el ``text`` del chat ya está acotado a
# 4000 chars (``ChatHttpRequest``); la respuesta del modelo puede ser más larga.
# Un cap holgado evita persistir blobs absurdos sin recortar contenido legítimo.
_MAX_TURN_CHARS = 32_768


class ConversationTurnCreate(YnaraBaseModel):
    """Payload para persistir un turno. El store cifra ``content`` antes del INSERT."""

    session_id: UUID
    role: TurnRole
    content: str = Field(min_length=1, max_length=_MAX_TURN_CHARS)
    seq: int = Field(ge=0)


class ConversationTurnOut(YnaraBaseModel):
    """Respuesta con ``content`` descifrado.

    PRECONDICIÓN DEL WRAPPER: ``ConversationTurnStore`` debe pasar ``content`` ya
    descifrado como ``str``. ``YnaraBaseModel.strict=True`` rechaza el ``BYTEA``
    crudo (defensa en profundidad).
    """

    id: UUID
    user_id: UUID
    session_id: UUID
    role: TurnRole
    content: str
    seq: int
    created_at: datetime
    updated_at: datetime
