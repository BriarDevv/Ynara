"""Pool de clientes LLM y estrategia de ruteo (M3).

El ``ClientPool`` agrupa varios ``LLMClient`` (uno por proceso de inferencia
— Ollama en 16GB / vLLM en 24GB+, ADR-014) y resuelve a que instancia mandar
una request segun el campo ``model``. La ``RoutingStrategy`` decide cual
candidato elegir cuando hay mas de uno que sirve el modelo.

Hoy la unica estrategia es ``FirstHealthy`` (toma el primero): alcanza
para 1-2 procesos. El gancho de escalado (ADR-009, plan §4) es
``LeastQueueDepth``, que rutearia por ``vllm:num_requests_waiting``; se
implementa cuando haya multiples instancias del mismo modelo, sin tocar
router ni cliente.

``build_pool`` arma el pool desde ``config.serving_endpoints`` (la lista
``LLM_SERVING`` describe la topologia, ADR-013). NO instancia clientes HTTP:
los recibe ya construidos (eso es responsabilidad del startup, M8), asi el
pool es testeable con ``FakeLlmClient``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.llm.clients.base import LLMClient
from app.llm.config import LlmRuntimeConfig
from app.llm.errors import ModelNotServedError


@runtime_checkable
class RoutingStrategy(Protocol):
    """Elige un candidato entre los clientes que sirven un modelo."""

    def pick(self, candidates: list[LLMClient]) -> LLMClient:
        """Devuelve el cliente elegido. ``candidates`` nunca esta vacio."""
        ...


class FirstHealthy:
    """Estrategia placeholder: devuelve el primer candidato.

    Asume que el pool ya entrega los candidatos en orden de preferencia
    (primario antes que secundario on-prem). ``LeastQueueDepth`` es el
    sucesor para escalar a N instancias por modelo (ADR-009, plan §4); no
    se implementa hasta que haga falta.
    """

    def pick(self, candidates: list[LLMClient]) -> LLMClient:
        return candidates[0]


class ClientPool:
    """Agrupa clientes LLM y rutea por modelo via ``serves_model``."""

    def __init__(self, clients: list[LLMClient], strategy: RoutingStrategy) -> None:
        """``clients`` en orden de preferencia (primario, luego secundario)."""
        self._clients = clients
        self._strategy = strategy

    @property
    def clients(self) -> list[LLMClient]:
        """Todos los clientes del pool, en orden de preferencia."""
        return self._clients

    def candidates(self, model: str) -> list[LLMClient]:
        """Clientes que sirven ``model``, preservando el orden del pool."""
        return [client for client in self._clients if client.serves_model(model)]

    def pick(self, model: str) -> LLMClient:
        """Elige un cliente para ``model`` via la estrategia.

        Levanta ``ModelNotServedError`` si ningun cliente sirve el modelo.
        """
        candidates = self.candidates(model)
        if not candidates:
            raise ModelNotServedError(model)
        return self._strategy.pick(candidates)

    async def aclose(self) -> None:
        """Cierra todos los clientes del pool (libera sus ``httpx.AsyncClient``).

        Lo llama ``ResilientClient.aclose`` en el teardown. Defensivo: salta los
        clientes sin ``aclose`` (p.ej. fakes minimos de tests), asi cerrar un
        pool de Fakes es inocuo.
        """
        for client in self._clients:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()


def build_pool(
    config: LlmRuntimeConfig,
    clients_by_base_url: dict[str, LLMClient],
) -> ClientPool:
    """Arma el ``ClientPool`` desde ``config.serving_endpoints`` (ADR-013).

    La lista ``LLM_SERVING`` describe la topologia: cada entrada es un proceso
    de inferencia (Ollama en 16GB / vLLM en 24GB+, ADR-014) — un ``base_url`` +
    los served_names que sirve. Ya no hay enum: N entradas = N procesos; varias
    entradas con el mismo served_name = N instancias del mismo modelo (escalado,
    ADR-009 §4).

    Los clientes ya vienen construidos en ``clients_by_base_url`` (keyed por
    base_url); este helper solo los ordena segun la lista. El orden importa: es
    el orden de preferencia (primero = primario, siguientes = fallback on-prem).
    Levanta ``KeyError`` si falta un cliente para una base_url declarada en
    ``serving_endpoints`` (config incoherente: fail-fast en el arranque).
    """
    clients = [clients_by_base_url[ep.base_url] for ep in config.serving_endpoints]
    return ClientPool(clients, FirstHealthy())
