"""Protocol estructural del cliente LLM, en capa ``core`` (ADR-011).

Rompe la única grieta ``core → feature-package`` del repo: antes ``core/deps.py``
importaba ``app.llm.clients.base.LLMClient`` para tipar ``get_llm_client``,
invirtiendo la dependencia sana (infra core dependiendo de ``app/llm/``). Acá
declaramos un ``typing.Protocol`` delgado que captura EXACTAMENTE el contrato que
``get_llm_client`` expone a sus callers (``complete`` / ``stream`` / ``health`` /
``serves_model``) — ni más ni menos.

La implementación concreta (``VllmClient``, ``FakeLlmClient``) y el ``Protocol``
canónico ``app.llm.clients.base.LLMClient`` satisfacen ESTE protocolo
**estructuralmente** (sin herencia): mismas firmas, mismos tipos. No se duplica
lógica, sólo la forma.

Los DTOs de las firmas (``ChatMessage`` / ``CompletionResult`` / ``CompletionChunk``
/ ``ModelHealth`` / ``ToolSpec``) viven en ``app.llm.schemas`` y se importan SÓLO
bajo ``TYPE_CHECKING``: con ``from __future__ import annotations`` toda anotación es
un string que nunca se evalúa en runtime, así que ``core`` queda **sin ningún import
de ``app.llm`` en runtime** (verificable con ``py_compile`` + inspección de imports),
mientras el type-checker conserva fidelidad total de tipos para el chequeo estructural.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.llm.schemas import (
        ChatMessage,
        CompletionChunk,
        CompletionResult,
        ModelHealth,
        ToolSpec,
    )


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Contrato estructural del cliente LLM que devuelve ``get_llm_client``.

    Réplica fiel de ``app.llm.clients.base.LLMClient`` (mismas 4 operaciones,
    mismas firmas), declarada en ``core`` para que ``deps.py`` no tenga que
    importar el feature-package ``app/llm/`` al tipar la dependencia. Cualquier
    implementación concreta lo satisface por duck typing.
    """

    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        thinking: bool | None = None,
        timeout_s: float | None = None,
    ) -> CompletionResult:
        """Genera una completion no-streaming (ver ``app.llm.clients.base``)."""
        ...

    def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        thinking: bool | None = None,
        timeout_s: float | None = None,
    ) -> AsyncIterator[CompletionChunk]:
        """Genera una completion en streaming (yield de chunks)."""
        ...

    async def health(self) -> ModelHealth:
        """Reporta si la instancia responde."""
        ...

    def serves_model(self, model: str) -> bool:
        """Indica si esta instancia sirve el modelo pedido."""
        ...
