"""Schemas HTTP del endpoint /v1/chat.

Contrato wire del chat: request/response del endpoint FastAPI, separado
de los schemas de dominio LLM (``app/llm/schemas.py``). Hereda
``YnaraBaseModel`` (strict=True, extra=forbid).

Mirror Zod: ``packages/shared-schemas/src/chat.ts``.

Nota de strict mode + el body de FastAPI (M9):
    El resto de los schemas hereda ``strict=True`` (``YnaraBaseModel``): no
    coerciona tipos en construccion Python. Pero el **request** que entra por
    HTTP es distinto: FastAPI parsea el body JSON a un ``dict`` de Python y
    valida con ``model_validate(dict)`` (NO ``model_validate_json`` sobre los
    bytes crudos). Bajo ``strict=True``, ese path RECHAZA ``mode`` y
    ``session_id`` como strings (un ``str`` no es instancia de ``Mode``/``UUID``)
    -> el front recibiria un 422 por mandar el wire documentado (mode y
    session_id como strings JSON). Por eso ``ChatHttpRequest`` relaja
    ``strict=False``: acepta la coercion de tipos wire (str->Mode, str->UUID)
    igual que lo haria ``model_validate_json``, manteniendo las constraints
    (``min_length``/``max_length``) y ``extra='forbid'``. Las responses
    (``Action`` / ``ChatHttpResponse``) siguen strict.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from app.enums import Mode
from app.schemas.base import YnaraBaseModel

CHAT_TEXT_MAX_LENGTH = 4000


class ChatHttpRequest(YnaraBaseModel):
    """Payload de ``POST /v1/chat`` (y ``POST /v1/chat/stream``).

    ``mode`` y ``session_id`` llegan como strings JSON desde el front. FastAPI
    valida el body con ``model_validate`` sobre el ``dict`` ya parseado; bajo el
    ``strict=True`` heredado eso rechazaria los strings wire (no son instancias
    de ``Mode``/``UUID``). Este schema override-a ``strict=False`` para aceptar
    la coercion de wire types (manteniendo constraints + ``extra='forbid'``);
    ver la nota del modulo.
    """

    # Override del strict heredado SOLO para el request wire: permite str->Mode /
    # str->UUID como manda el front por HTTP. Constraints y extra=forbid siguen.
    model_config = ConfigDict(
        strict=False,
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )

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
