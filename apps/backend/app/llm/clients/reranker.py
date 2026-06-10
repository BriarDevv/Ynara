"""Cliente de reranking: Protocol + Fake determinista (prerequisito de M7/M8).

``Reranker`` es el contrato para reordenar documentos candidatos tras la
búsqueda ANN (top-K pgvector). Hay dos implementaciones: el ``FakeReranker``
passthrough (default dev/test) y el ``VllmReranker`` real contra la API
``/rerank`` de vLLM; la factory elige por ``RERANKER_BACKEND`` (fake|vllm).
Ollama no sirve cross-encoders, así que en dev se usa el Fake.

``RerankResult`` encapsula el índice original y el score asignado, para que
el caller pueda reconstruir el orden sin requerir que los documentos se
dupliquen en la respuesta.

``FakeReranker`` preserva el orden de entrada (el orden del ANN), asignando
scores descendentes estables ``1.0 - index * 1e-3``. Es determinista, sin
red y respeta ``top_n``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from app.llm.clients._http_status import raise_for_status
from app.llm.errors import LlmError, LlmTimeoutError, LlmUnavailableError
from app.llm.schemas import ModelHealth

_RERANK_PATH = "/rerank"
_MODELS_PATH = "/models"


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


class VllmReranker:
    """Implementa ``Reranker`` contra la API ``/rerank`` de vLLM (cross-encoder).

    Habla el contrato rerank estilo Cohere/Jina que expone vLLM en
    ``/v1/rerank`` (``{"model","query","documents","top_n"}`` ->
    ``{"results":[{"index","relevance_score"}]}``). Recibe el
    ``httpx.AsyncClient`` por constructor -> testeable con ``httpx.MockTransport``
    sin red. Nunca importa FastAPI ni vLLM; nunca loguea ni propaga
    ``query``/``documents`` (regla #4): los errores son etiquetas tecnicas fijas.

    Ollama NO sirve cross-encoders: este cliente apunta a vLLM. En dev se usa el
    ``FakeReranker`` (ver factory + ``RERANKER_BACKEND``).
    """

    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.AsyncClient,
        model: str = "bge-reranker-v2-m3",
        default_timeout_s: float = 30.0,
    ) -> None:
        """Un ``VllmReranker`` = un servidor de reranking.

        El ``httpx.AsyncClient`` se construye afuera (la factory) y este cliente
        queda como su owner para el cierre (``aclose``), evitando fuga de sockets.
        """
        self._base_url = base_url.rstrip("/")
        self._http = http_client
        self._model = model
        self._default_timeout_s = default_timeout_s

    async def aclose(self) -> None:
        """Cierra el ``httpx.AsyncClient`` subyacente (lo llama el lifespan)."""
        await self._http.aclose()

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        # Sin documentos no hay nada que reordenar: cortamos sin red (mismo
        # contrato que ``FakeReranker``).
        if not documents:
            return []
        payload: dict[str, Any] = {
            "model": self._model,
            "query": query,
            "documents": list(documents),
        }
        if top_n is not None:
            payload["top_n"] = top_n
        response = await self._post(_RERANK_PATH, payload, self._default_timeout_s)
        raise_for_status(response)
        return self._parse_results(response.json(), top_n=top_n)

    async def health(self) -> ModelHealth:
        url = f"{self._base_url}{_MODELS_PATH}"
        try:
            response = await self._http.get(url, timeout=5.0)
        except (httpx.TimeoutException, httpx.TransportError):
            return ModelHealth(model_name=self._model, healthy=False)
        return ModelHealth(
            model_name=self._model,
            healthy=response.status_code == httpx.codes.OK,
        )

    async def _post(self, path: str, payload: dict[str, Any], timeout_s: float) -> httpx.Response:
        url = f"{self._base_url}{path}"
        try:
            return await self._http.post(url, json=payload, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            # Etiqueta fija: el mensaje de httpx trae el host (regla #4).
            raise LlmTimeoutError("timeout HTTP") from exc
        except httpx.ConnectError as exc:
            raise LlmUnavailableError("connect error") from exc

    @staticmethod
    def _parse_results(body: dict[str, Any], *, top_n: int | None) -> list[RerankResult]:
        raw = body.get("results")
        if not isinstance(raw, list):
            # Respuesta sin ``results``: no exponemos el body (regla #4).
            raise LlmError("respuesta de rerank malformada")
        try:
            results = [
                RerankResult(
                    index=int(item["index"]),
                    score=float(item["relevance_score"]),
                )
                for item in raw
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise LlmError("respuesta de rerank malformada") from exc
        # vLLM ya ordena por score desc; reordenamos defensivamente.
        results.sort(key=lambda r: r.score, reverse=True)
        if top_n is not None:
            results = results[:top_n]
        return results
