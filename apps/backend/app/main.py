"""Entrypoint de FastAPI.

Levanta la app, registra middlewares y monta routers de la API v1.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import health
from app.core.config import get_settings
from app.core.observability import init_sentry
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.config import load_llm_config

settings = get_settings()

# Error tracking: no-op si no hay SENTRY_DSN. Antes de crear la app para
# capturar errores de startup. El before_send limpia PII (regla #4).
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de startup/shutdown.

    Construye los clientes LLM/embedder/reranker como singletons en
    ``app.state`` para que las deps de FastAPI los inyecten sin recrearlos
    por request.  Usando los *served_name* del config (p.ej. 'qwen', 'gemma4'),
    NO las keys del dict de modelos.

    TODO: swap por ResilientClient / VllmEmbeddingClient cuando vLLM esté
    disponible — solo cambia este bloque; el resto del stack no toca.
    TODO: warm-up del LLM router, conexión a Redis, etc.
    """
    # startup — clientes como singletons
    cfg = load_llm_config()
    served_models = frozenset(m.served_name for m in cfg.models.values())
    app.state.llm_client = FakeLlmClient(served_models=served_models)
    app.state.embedder = FakeEmbeddingClient()
    app.state.reranker = FakeReranker()

    yield

    # shutdown (actualmente no-op; cerrar conexiones reales aquí cuando existan)


app = FastAPI(
    title="Ynara API",
    version=__version__,
    description="API del asistente personal Ynara.",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# CORS: en producción solo los dominios de web/mobile.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1", tags=["health"])

# TODO: agregar routers de auth, memory, sessions cuando estén.
