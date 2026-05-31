"""Schemas HTTP del endpoint /v1/chat.

Contrato wire del chat: request/response del endpoint FastAPI, separado
de los schemas de dominio LLM (``app/llm/schemas.py``). Hereda
``YnaraBaseModel`` (strict=True, extra=forbid).

Mirror Zod: ``packages/shared-schemas/src/chat.ts``.

Nota de strict mode + JSON:
    ``strict=True`` aplica en construccion Python (``Model(**kwargs)``).
    Cuando FastAPI deserializa el body JSON usa ``model_validate`` con
    mode='json' (lax para tipos wire como str->UUID, str->Mode), por lo
    que el front puede mandar ``session_id`` como string UUID y ``mode``
    como string sin que strict los rechace. Los tests documentan este
    comportamiento con ``model_validate(..., context={'mode': 'json'})``
    o ``model_validate_json``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.enums import Mode
from app.schemas.base import YnaraBaseModel

CHAT_TEXT_MAX_LENGTH = 4000


class ChatHttpRequest(YnaraBaseModel):
    """Payload de ``POST /v1/chat`` (y ``POST /v1/chat/stream``).

    ``session_id`` llega como UUID string desde el front (JSON wire);
    FastAPI / model_validate_json lo castea a UUID antes de la
    validacion strict.
    """

    text: str = Field(min_length=1, max_length=CHAT_TEXT_MAX_LENGTH)
    mode: Mode
    session_id: UUID | None = None


class Action(YnaraBaseModel):
    """Una accion ejecutada por el agente (tool call + resultado).

    Alinea con ``ActionSchema`` de ``chat.ts``:
    ``{ id, name, arguments, result }``.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class ChatHttpResponse(YnaraBaseModel):
    """Response de ``POST /v1/chat``.

    ``finish_reason`` es ``None`` hasta que el tool loop lo surfacee
    (prerequisito duro para el evento ``done`` SSE).
    """

    text: str
    actions: list[Action] = Field(default_factory=list)
    session_id: UUID
    finish_reason: str | None = None
