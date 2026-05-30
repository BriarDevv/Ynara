"""Cliente de embeddings: Protocol + Fake determinista (prerequisito de M7/M8).

``EmbeddingClient`` es el contrato para computar los ``Vector(1024)`` de
``semantic_memory.content_embedding`` y ``episodic_memory.summary_embedding``
(bge-m3 on-prem, ADR-008). Espeja el estilo de ``LLMClient`` (``base.py``):
``runtime_checkable``, async, sin herencia, inyectable por constructor.

``FakeEmbeddingClient`` produce vectores **deterministas** (mismo texto → mismo
vector) sin red ni GPU — mismo rol que ``FakeLlmClient`` para los tests de la
capa de memoria. NO modela similitud semántica real: solo garantiza dimensión
1024, determinismo y rango acotado. El ``VllmEmbeddingClient`` real (contra
``POST /v1/embeddings`` de vLLM) se implementa en un milestone aparte gateado por
la disponibilidad del servidor de bge-m3 (ADR-009), igual que ``FakeLlmClient``
(M2) precedió a ``VllmClient`` (M3).
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from app.llm.schemas import ModelHealth

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
