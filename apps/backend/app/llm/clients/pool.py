"""Pool de clientes LLM y estrategia de ruteo (M3).

El ``ClientPool`` agrupa varios ``LLMClient`` (uno por proceso vLLM,
ADR-009 D1) y resuelve a que instancia mandar una request segun el campo
``model``. La ``RoutingStrategy`` decide cual candidato elegir cuando hay
mas de uno que sirve el modelo.

Hoy la unica estrategia es ``FirstHealthy`` (toma el primero): alcanza
para 1-2 procesos. El gancho de escalado (ADR-009, plan §4) es
``LeastQueueDepth``, que rutearia por ``vllm:num_requests_waiting``; se
implementa cuando haya multiples instancias del mismo modelo, sin tocar
router ni cliente.

``build_pool`` arma el pool segun la topologia configurada. NO instancia
clientes HTTP: los recibe ya construidos (eso es responsabilidad del
startup, M8), asi el pool es testeable con ``FakeLlmClient``.
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


def build_pool(
    config: LlmRuntimeConfig,
    clients_by_base_url: dict[str, LLMClient],
) -> ClientPool:
    """Arma el ``ClientPool`` segun la topologia de ``config``.

    Mapeo topologia -> clientes (ADR-009 D1):

    - ``split_process`` — 2 procesos: ``primary_base_url`` (primario) y
      ``secondary_base_url`` (secundario on-prem para fallback).
    - ``single_process`` / ``swap_lru`` — 1 proceso: solo
      ``primary_base_url``.

    Los clientes ya vienen construidos en ``clients_by_base_url`` (keyed por
    base_url); este helper solo los ordena. El orden importa: el primero es
    el primario, el segundo (si hay) es el fallback on-prem. Levanta
    ``KeyError`` si falta un cliente para una base_url requerida por la
    topologia (config incoherente: fail-fast en el arranque).
    """
    primary = clients_by_base_url[config.primary_base_url]
    if config.topology == "split_process":
        secondary = clients_by_base_url[config.secondary_base_url]
        clients = [primary, secondary]
    else:
        clients = [primary]
    return ClientPool(clients, FirstHealthy())
