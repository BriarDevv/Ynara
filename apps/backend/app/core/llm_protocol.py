"""Protocols estructurales de los clientes LLM en capa ``core`` (ADR-011).

Cierra la grieta ``core → feature-package`` del repo: antes ``core/deps.py``
importaba ``app.llm.clients.*`` (``LLMClient`` / ``EmbeddingClient`` / ``Reranker``)
para tipar ``get_llm_client`` / ``get_embedder`` / ``get_reranker``, invirtiendo la
dependencia sana (infra core dependiendo de ``app/llm/``). Acá declaramos
``typing.Protocol`` delgados que capturan EXACTAMENTE el contrato que cada getter
expone a sus callers — ni más ni menos. Tras esto ``core/deps.py`` no importa
``app.llm`` en runtime. Los wrappers de memoria (``app/memory/``) siguen importando
las clases concretas: eso es ``feature → feature`` (permitido), no ``core → feature``.

Las implementaciones concretas (``VllmClient``/``FakeLlmClient``, los embedders y
rerankers Fake/Vllm) y los ``Protocol`` canónicos de ``app.llm.clients.*`` satisfacen
ESTOS protocolos **estructuralmente** (sin herencia): mismas firmas, mismos tipos. No
se duplica lógica, sólo la forma.

Los DTOs de las firmas (``ChatMessage`` / ``CompletionResult`` / ``CompletionChunk``
/ ``ModelHealth`` / ``ToolSpec`` / ``RerankResult``) viven en ``app.llm`` y se importan
SÓLO bajo ``TYPE_CHECKING``: con ``from __future__ import annotations`` toda anotación
es un string que nunca se evalúa en runtime, así que ``core`` queda **sin ningún import
de ``app.llm`` en runtime** (verificable con ``py_compile`` + inspección de imports),
mientras el type-checker conserva fidelidad total de tipos para el chequeo estructural.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.llm.clients.reranker import RerankResult
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


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    """Contrato estructural del cliente de embeddings que devuelve ``get_embedder``.

    Réplica fiel de ``app.llm.clients.embedding.EmbeddingClient`` (``embed`` +
    ``health``), declarada en ``core`` para que ``deps.py`` no importe ``app/llm/``.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden (dim = 1024)."""
        ...

    async def health(self) -> ModelHealth:
        """Reporta si el backend de embeddings responde."""
        ...


@runtime_checkable
class RerankerProtocol(Protocol):
    """Contrato estructural del reranker que devuelve ``get_reranker``.

    Réplica fiel de ``app.llm.clients.reranker.Reranker`` (``rerank`` + ``health``),
    declarada en ``core`` para que ``deps.py`` no importe ``app/llm/``.
    """

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """Reordena ``documents`` por relevancia descendente (ver ``app.llm.clients.reranker``)."""
        ...

    async def health(self) -> ModelHealth:
        """Reporta si el backend de reranking responde."""
        ...
