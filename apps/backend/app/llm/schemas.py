"""Schemas de la capa LLM (M1).

Tipos de dominio del cliente de inferencia, independientes de FastAPI y de
vLLM. ``ChatRequest`` / ``ChatResponse`` son el contrato del router (se
movieron desde ``router.py``); el resto modela lo que el cliente manda al
servidor y lo que devuelve, en formato neutro (no OpenAI ni custom de
modelo).

``CompletionResult`` / ``CompletionChunk`` / ``ModelHealth`` son
``frozen`` + ``strict``: son resultados inmutables que viajan del cliente
al router sin mutarse.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import Mode

Role = Literal["system", "user", "assistant", "tool"]


# ---------- Contrato del router ----------


class ChatRequest(BaseModel):
    """Entrada del router: texto del usuario + modo activo."""

    text: str
    mode: Mode
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Salida del router hacia el caller HTTP."""

    text: str
    actions: list[dict[str, Any]] = []
    session_id: str


# ---------- Mensajes y tools ----------


class ChatMessage(BaseModel):
    """Un turno del historial. ``content`` puede ser ``None`` cuando el
    assistant solo emite tool_calls; ``tool_call_id`` / ``name`` aplican al
    rol ``tool`` (resultado de una tool)."""

    model_config = ConfigDict(strict=True)

    role: Role
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ToolSpec(BaseModel):
    """Especificacion de una tool en formato OpenAI (``parameters`` es un
    JSON schema)."""

    model_config = ConfigDict(strict=True)

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    """Una tool call ya normalizada: ``arguments`` viene parseado de JSON a
    dict (a diferencia del wire OpenAI, donde es un string)."""

    model_config = ConfigDict(strict=True, frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


# ---------- Resultados de inferencia ----------


class CompletionResult(BaseModel):
    """Resultado de una completion no-streaming (inmutable)."""

    model_config = ConfigDict(strict=True, frozen=True)

    text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    model_name: str
    latency_ms: float


class CompletionChunk(BaseModel):
    """Un fragmento de un stream (inmutable). ``tool_call_delta`` es el
    fragmento crudo OpenAI de la tool call en curso, si lo hay."""

    model_config = ConfigDict(strict=True, frozen=True)

    delta_text: str
    tool_call_delta: dict[str, Any] | None = None
    finish_reason: str | None = None


class ModelHealth(BaseModel):
    """Estado de salud reportado por una instancia de modelo."""

    model_config = ConfigDict(strict=True, frozen=True)

    model_name: str
    healthy: bool
