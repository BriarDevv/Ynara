"""Cliente de reranking: Protocol + Fake determinista (prerequisito de M7/M8).

``Reranker`` es el contrato para reordenar documentos candidatos tras la
búsqueda ANN (top-K pgvector). En M7 se usa solo el ``FakeReranker``
passthrough; la implementación real contra un endpoint (cross-encoder vía
vLLM / Cohere) se conecta en un milestone separado, igual que ``VllmClient``
precedió a ``FakeLlmClient``.

``RerankResult`` encapsula el índice original y el score asignado, para que
el caller pueda reconstruir el orden sin requerir que los documentos se
dupliquen en la respuesta.

``FakeReranker`` preserva el orden de entrada (el orden del ANN), asignando
scores descendentes estables ``1.0 - index * 1e-3``. Es determinista, sin
red y respeta ``top_n``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.llm.schemas import ModelHealth


@dataclass(frozen=True)
class RerankResult:
    """Posición original y score asignado por el reranker.

    ``index`` referencia la posición en la lista ``documents`` que se pasó a
    ``rerank``; ``score`` es un float en ``[0, 1]`` (mayor → más relevante).
    """

    index: int
    score: float


@runtime_checkable
class Reranker(Protocol):
    """Contrato del cliente de reranking que consume la capa de memoria."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """Devuelve los documentos ordenados por relevancia descendente.

        Args:
            query: La consulta de búsqueda.
            documents: Candidatos a reordenar (texto plano, ya descifrado).
            top_n: Si se pasa, recorta la lista a los ``top_n`` mejores.
                   ``None`` devuelve todos.

        Returns:
            Lista de ``RerankResult`` ordenada por ``score`` descendente,
            con longitud ``min(top_n, len(documents))`` si ``top_n`` no es
            ``None``, o ``len(documents)`` en caso contrario.
        """
        ...

    async def health(self) -> ModelHealth:
        """Reporta si el backend de reranking responde."""
        ...


class FakeReranker:
    """Implementa ``Reranker`` como passthrough determinista para tests.

    Preserva el orden de entrada (el orden del ANN pgvector), asignando
    scores descendentes estables: ``score = 1.0 - index * 1e-3``. No usa
    red ni modelos. Respeta ``top_n``.

    El atributo ``rerank_calls`` acumula los argumentos de cada llamada para
    que los tests de M7 puedan verificar cuántas veces se invocó el reranker
    y con qué argumentos.
    """

    def __init__(self, *, model: str = "fake-reranker") -> None:
        self._model = model
        self._healthy = True
        self.rerank_calls: list[dict[str, object]] = []

    def set_health(self, healthy: bool) -> None:
        self._healthy = healthy

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        self.rerank_calls.append({"query": query, "documents": list(documents), "top_n": top_n})

        results = [RerankResult(index=i, score=1.0 - i * 1e-3) for i in range(len(documents))]

        if top_n is not None:
            results = results[:top_n]

        return results

    async def health(self) -> ModelHealth:
        return ModelHealth(model_name=self._model, healthy=self._healthy)
