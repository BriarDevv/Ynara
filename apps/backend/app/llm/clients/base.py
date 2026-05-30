"""Protocols de la capa de clientes LLM (M1).

``LLMClient`` es el contrato que el router consume; cualquier
implementacion concreta (``VllmClient``, ``FakeLlmClient``) lo satisface
por duck typing. ``ToolCallParser`` abstrae como se normalizan las tool
calls de la respuesta del servidor.

Ambos son ``runtime_checkable`` para poder afirmar conformidad en tests sin
heredar explicitamente.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Protocol, runtime_checkable

from app.llm.schemas import (
    ChatMessage,
    CompletionChunk,
    CompletionResult,
    ModelHealth,
    ToolCall,
    ToolSpec,
)


@runtime_checkable
class ToolCallParser(Protocol):
    """Normaliza tool calls de la respuesta del servidor a ``ToolCall``.

    vLLM ya devuelve las tool calls en formato OpenAI estandar (sin importar
    el modelo); el parser solo las re-empaqueta y parsea el JSON de
    ``arguments``.
    """

    def parse(self, raw_message: dict[str, object]) -> list[ToolCall]:
        """Extrae las tool calls de un ``message`` OpenAI no-streaming."""
        ...

    def accumulate(self, deltas: Iterable[dict[str, object]]) -> list[ToolCall]:
        """Junta fragmentos de tool calls de un stream en ``ToolCall``s."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """Contrato del cliente de inferencia que consume el router."""

    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float | None = None,
    ) -> CompletionResult:
        """Genera una completion no-streaming.

        ``timeout_s=None`` deja que la implementacion use su default (el
        ``VllmClient`` lo toma de ``config.serving.request_timeout_s``).
        """
        ...

    def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float | None = None,
    ) -> AsyncIterator[CompletionChunk]:
        """Genera una completion en streaming (yield de chunks).

        ``timeout_s=None`` -> default de la implementacion (ver ``complete``).
        """
        ...

    async def health(self) -> ModelHealth:
        """Reporta si la instancia responde."""
        ...

    def serves_model(self, model: str) -> bool:
        """Indica si esta instancia sirve el modelo pedido."""
        ...
