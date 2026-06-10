"""Cliente de embeddings: Protocol + Fake determinista (prerequisito de M7/M8).

``EmbeddingClient`` es el contrato para computar los ``Vector(1024)`` de
``semantic_memory.content_embedding`` y ``episodic_memory.summary_embedding``
(bge-m3 on-prem, ADR-008). Espeja el estilo de ``LLMClient`` (``base.py``):
``runtime_checkable``, async, sin herencia, inyectable por constructor.

``FakeEmbeddingClient`` produce vectores **deterministas** (mismo texto → mismo
vector) sin red ni GPU — mismo rol que ``FakeLlmClient`` para los tests de la
capa de memoria. NO modela similitud semántica real: solo garantiza dimensión
1024, determinismo y rango acotado. El ``VllmEmbeddingClient`` real (contra
``POST /v1/embeddings`` de vLLM/Ollama, bge-m3 ADR-009) vive abajo en este mismo
módulo; la factory elige entre ambos por ``EMBEDDING_BACKEND`` (fake|vllm).
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

import httpx

from app.llm.clients._http_status import raise_for_status
from app.llm.errors import LlmError, LlmTimeoutError, LlmUnavailableError
from app.llm.schemas import ModelHealth

_EMBEDDINGS_PATH = "/embeddings"
_MODELS_PATH = "/models"

# bge-m3 dense, ADR-008. Constante local a propósito (no se importa de
# models.memory): la capa de clientes LLM no debe arrastrar SQLAlchemy/los
# modelos sagrados al importarse (ni sus tests). El valor 1024 es estable hasta
# un ADR nuevo; si cambia, cambia en ambos lados con su gate sagrado.
EMBEDDING_DIM = 1024


@runtime_checkable
class EmbeddingClient(Protocol):
    """Contrato del cliente de embeddings que consumen los wrappers de memoria."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden. Dimensión = 1024."""
        ...

    async def health(self) -> ModelHealth:
        """Reporta si el backend de embeddings responde."""
        ...


class FakeEmbeddingClient:
    """Implementa ``EmbeddingClient`` con vectores deterministas para tests.

    El vector de un texto se deriva expandiendo ``sha256(text)`` hasta ``dim``
    floats en ``[-1, 1]``: mismo texto → mismo vector, textos distintos →
    vectores distintos. Reproducible sin red ni GPU.
    """

    def __init__(self, *, dim: int = EMBEDDING_DIM, model: str = "bge-m3") -> None:
        self._dim = dim
        self._model = model
        self._healthy = True
        self.embed_calls: list[list[str]] = []

    def set_health(self, healthy: bool) -> None:
        self._healthy = healthy

    def _vector_for(self, text: str) -> list[float]:
        out: list[float] = []
        counter = 0
        while len(out) < self._dim:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for byte in digest:
                out.append((byte / 127.5) - 1.0)  # 0..255 -> [-1, 1]
                if len(out) >= self._dim:
                    break
            counter += 1
        return out

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        return [self._vector_for(text) for text in texts]

    async def health(self) -> ModelHealth:
        return ModelHealth(model_name=self._model, healthy=self._healthy)


class VllmEmbeddingClient:
    """Implementa ``EmbeddingClient`` contra ``POST /v1/embeddings`` de vLLM.

    Habla la API de embeddings OpenAI-compatible, asi que sirve igual contra un
    vLLM real (bge-m3, ADR-009) o un Ollama local (mismo endpoint). Recibe el
    ``httpx.AsyncClient`` por constructor -> testeable con ``httpx.MockTransport``
    sin red. Nunca importa FastAPI ni vLLM; nunca loguea ni propaga el texto del
    usuario (regla #4): los errores son etiquetas tecnicas fijas.

    Mapeo de errores HTTP a la taxonomia (``app/llm/errors.py``), via el helper
    compartido ``_http_status.raise_for_status``:

    - timeout       -> ``LlmTimeoutError``
    - ConnectError  -> ``LlmUnavailableError``
    - 429           -> ``LlmOverloadedError``
    - 400 / 422     -> ``LlmBadRequestError``
    - 503 / >= 500  -> ``LlmUnavailableError``
    """

    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.AsyncClient,
        model: str = "bge-m3",
        default_timeout_s: float = 30.0,
    ) -> None:
        """Un ``VllmEmbeddingClient`` = un servidor de embeddings.

        ``model`` es el nombre publicado por el server (``EMBEDDING_MODEL``);
        viaja en el campo ``model`` del payload OpenAI. El ``httpx.AsyncClient``
        se construye afuera (la factory) y este cliente queda como su owner para
        el cierre (``aclose``), evitando fuga de sockets en prod.
        """
        self._base_url = base_url.rstrip("/")
        self._http = http_client
        self._model = model
        self._default_timeout_s = default_timeout_s

    async def aclose(self) -> None:
        """Cierra el ``httpx.AsyncClient`` subyacente (lo llama el lifespan)."""
        await self._http.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Batch vacio: la API OpenAI rechaza ``input`` vacio; cortamos sin red
        # (mismo contrato que ``FakeEmbeddingClient.embed([]) == []``).
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self._model, "input": list(texts)}
        response = await self._post(_EMBEDDINGS_PATH, payload, self._default_timeout_s)
        raise_for_status(response)
        return self._parse_embeddings(response.json(), expected=len(texts))

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
    def _parse_embeddings(body: dict[str, Any], *, expected: int) -> list[list[float]]:
        data = body.get("data")
        if not isinstance(data, list) or len(data) != expected:
            # Respuesta incoherente con el request: no exponemos el body (regla #4).
            raise LlmError("respuesta de embeddings malformada")
        try:
            # La API OpenAI garantiza orden por ``index``; ordenamos defensivamente.
            ordered = sorted(data, key=lambda item: item["index"])
            return [list(item["embedding"]) for item in ordered]
        except (KeyError, TypeError) as exc:
            raise LlmError("respuesta de embeddings malformada") from exc
