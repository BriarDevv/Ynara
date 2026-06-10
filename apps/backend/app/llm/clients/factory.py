"""Factory de clientes LLM / embedder / reranker (P2 — mata el dead-code de runtime).

Hasta P2, ``ResilientClient`` / ``ClientPool`` / ``build_pool`` / ``VllmClient``
estaban implementados y testeados pero NINGUN path de prod los instanciaba: el
lifespan (``app/main.py``) y los helpers de ``consolidation`` HARDCODEABAN los
Fakes incluso en la rama de serving real. Esta factory centraliza la decision:

- En dev/test (default, sin GPU) -> los Fakes deterministas (sin red, sin boot
  roto, sin intentos de conexion a vLLM).
- Cuando la config pide serving real (``llm_backend == "vllm"`` o
  ``environment == "production"`` para el LLM; ``embedding_backend == "vllm"``
  para el embedder; ``reranker_backend == "vllm"`` para el reranker) -> los
  clientes REALES (``ResilientClient(build_pool(VllmClient...))``,
  ``VllmEmbeddingClient``, ``VllmReranker``).

Los Fakes quedan DETRAS de la condicion, NO hardcodeados: cambiar a serving real
es flippear settings, no editar el lifespan. La factory NO abre conexiones de red
al construirse (``httpx.AsyncClient`` con un transport perezoso no disca hasta el
primer request), asi que es seguro instanciarla en el arranque aunque vLLM no este
levantado todavia; el ``ResilientClient`` degrada por diseno si las instancias no
responden (regla #4: fallback SIEMPRE on-prem, cero APIs externas).

No importa FastAPI (regla de capas): solo ``Settings`` + ``LlmRuntimeConfig`` +
``httpx`` + los clientes de ``app.llm.clients``.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import (
    EmbeddingClient,
    FakeEmbeddingClient,
    VllmEmbeddingClient,
)
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.parsers import OpenAIToolCallParser
from app.llm.clients.pool import build_pool
from app.llm.clients.reranker import FakeReranker, Reranker, VllmReranker
from app.llm.clients.resilient import ResilientClient
from app.llm.clients.vllm import VllmClient
from app.llm.config import LlmRuntimeConfig


def _wants_real_llm(settings: Settings) -> bool:
    """Decide si construir el LLM real (vLLM) o el Fake determinista.

    Serving real cuando ``LLM_BACKEND=vllm`` (opt-in explicito: dev contra Ollama
    o un vLLM local) o en ``production`` (siempre real). dev/staging/test sin el
    flag corren con los Fakes (sin discar a vLLM). El flag desacopla "serving
    real" de "soy prod" para no mentir ``environment`` (que dispara los fail-fast
    de prod: JWT fuerte, CORS no-localhost, master key).
    """
    return settings.llm_backend == "vllm" or settings.environment == "production"


def build_llm_client(settings: Settings, config: LlmRuntimeConfig) -> LLMClient:
    """Construye el cliente LLM segun la config: ``ResilientClient`` real o Fake.

    Camino real (``_wants_real_llm``): un ``VllmClient`` por base_url de la
    topologia (cada uno = un proceso vLLM, ADR-009 D1), todos sirviendo el set
    de ``served_name`` de la config; se arman en un ``ClientPool`` via
    ``build_pool`` (que ordena primario/secundario segun ``topology``) y se
    envuelven en un ``ResilientClient`` (retry + breaker + fallback on-prem).

    Camino Fake (default dev/test): ``FakeLlmClient`` con los ``served_name`` de
    la config, igual que el comportamiento historico del lifespan. No abre red.
    """
    served_models = frozenset(m.served_name for m in config.models.values())
    if not _wants_real_llm(settings):
        return FakeLlmClient(served_models=served_models)

    # Serving real: un VllmClient por base_url QUE LA TOPOLOGIA USA (no mas).
    # split_process necesita primary+secondary (fallback on-prem); single_process
    # y swap_lru usan solo el primary. Construir el secondary en esas dos ultimas
    # dejaria un VllmClient + httpx.AsyncClient huerfano (fuera del pool, nunca
    # cerrado): derivar el set ANTES de construir evita esa fuga.
    parser = OpenAIToolCallParser()
    timeout_s = float(config.serving.request_timeout_s)
    if config.topology == "split_process":
        base_urls = {config.primary_base_url, config.secondary_base_url}
    else:
        base_urls = {config.primary_base_url}
    clients_by_base_url: dict[str, LLMClient] = {
        base_url: VllmClient(
            base_url=base_url,
            served_models=served_models,
            http_client=httpx.AsyncClient(),
            parser=parser,
            default_timeout_s=timeout_s,
        )
        for base_url in base_urls
    }
    pool = build_pool(config, clients_by_base_url)
    return ResilientClient(pool)


def build_embedder(settings: Settings) -> EmbeddingClient:
    """Construye el cliente de embeddings segun ``embedding_backend``.

    ``vllm`` -> ``VllmEmbeddingClient`` real contra ``settings.embedding_base_url``
    (``POST /v1/embeddings``, bge-m3; sirve igual a un vLLM real o a Ollama). No
    abre red al construirse (``httpx.AsyncClient`` perezoso), asi que es seguro
    instanciarlo en el arranque aunque el server no este levantado todavia.

    ``fake`` (default operativo, sin GPU) -> ``FakeEmbeddingClient``.
    """
    if settings.embedding_backend == "vllm":
        return VllmEmbeddingClient(
            base_url=settings.embedding_base_url,
            http_client=httpx.AsyncClient(),
            model=settings.embedding_model,
        )
    return FakeEmbeddingClient(model=settings.embedding_model)


def build_reranker(settings: Settings) -> Reranker:
    """Construye el reranker segun ``reranker_backend``.

    ``vllm`` -> ``VllmReranker`` real contra ``settings.reranker_base_url`` (API
    ``/rerank`` de vLLM). Ollama no sirve cross-encoders, asi que en dev se deja
    en ``fake``. No abre red al construirse (``httpx.AsyncClient`` perezoso).

    ``fake`` (default) -> ``FakeReranker`` passthrough.
    """
    if settings.reranker_backend == "vllm":
        return VllmReranker(
            base_url=settings.reranker_base_url,
            http_client=httpx.AsyncClient(),
            model=settings.reranker_model,
        )
    return FakeReranker()


def build_llm_clients(
    settings: Settings, config: LlmRuntimeConfig
) -> tuple[LLMClient, EmbeddingClient, Reranker]:
    """Construye los tres clientes de una (``llm_client``, ``embedder``, ``reranker``).

    Helper de conveniencia para el lifespan: una sola llamada arma el trio de
    singletons. Cada uno se gatea de forma independiente (ver ``build_llm_client``
    / ``build_embedder`` / ``build_reranker``).
    """
    return (
        build_llm_client(settings, config),
        build_embedder(settings),
        build_reranker(settings),
    )
