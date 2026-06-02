"""Cliente LLM falso y programable para tests (M2).

``FakeLlmClient`` implementa ``LLMClient`` sin red: se le programan las
respuestas (o errores) que debe devolver. Vive en ``app/`` (no en
``tests/``) para reusarlo en los tests del router y del pool de milestones
futuros (M3+).

Uso tipico::

    fake = FakeLlmClient(served_models=frozenset({"qwen-3.5-9b"}))
    fake.queue_result(CompletionResult(...))
    result = await fake.complete(model="qwen-3.5-9b", messages=[...])

Si se programa una excepcion, ``complete`` la levanta. Por default
``health`` reporta sano; se puede forzar con ``set_health``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator

from app.llm.schemas import (
    ChatMessage,
    CompletionChunk,
    CompletionResult,
    ModelHealth,
    ToolSpec,
)


class FakeLlmClient:
    """Implementa ``LLMClient`` con respuestas programables."""

    def __init__(self, *, served_models: frozenset[str]) -> None:
        self._served_models = served_models
        self._results: deque[CompletionResult | Exception] = deque()
        self._chunks: deque[list[CompletionChunk] | Exception] = deque()
        self._healthy = True
        self.complete_calls: list[dict[str, object]] = []
        self.stream_calls: list[dict[str, object]] = []

    # ---------- programacion ----------

    def queue_result(self, result: CompletionResult) -> None:
        """Encola un resultado para la proxima llamada a ``complete``."""
        self._results.append(result)

    def queue_error(self, error: Exception) -> None:
        """Encola un error para la proxima llamada a ``complete``."""
        self._results.append(error)

    def queue_chunks(self, chunks: list[CompletionChunk]) -> None:
        """Encola una secuencia de chunks para la proxima llamada a
        ``stream``."""
        self._chunks.append(chunks)

    def queue_stream_error(self, error: Exception) -> None:
        """Encola un error para la proxima llamada a ``stream``."""
        self._chunks.append(error)

    def set_health(self, healthy: bool) -> None:
        self._healthy = healthy

    # ---------- contrato LLMClient ----------

    def serves_model(self, model: str) -> bool:
        return model in self._served_models

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
        self.complete_calls.append({"model": model, "messages": messages, "tools": tools})
        if not self._results:
            raise AssertionError("FakeLlmClient: no hay resultados programados")
        item = self._results.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    async def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float | None = None,
    ) -> AsyncIterator[CompletionChunk]:
        self.stream_calls.append({"model": model, "messages": messages, "tools": tools})
        if not self._chunks:
            raise AssertionError("FakeLlmClient: no hay chunks programados")
        item = self._chunks.popleft()
        if isinstance(item, Exception):
            raise item
        for chunk in item:
            yield chunk

    async def health(self) -> ModelHealth:
        model_name = next(iter(self._served_models), "")
        return ModelHealth(model_name=model_name, healthy=self._healthy)

    async def aclose(self) -> None:
        """No-op: el Fake no tiene recursos de red que liberar.

        Existe para que el teardown del lifespan/pool cierre el cliente LLM de
        forma uniforme sea Fake o real (``ResilientClient``/``VllmClient``).
        """
        return None
