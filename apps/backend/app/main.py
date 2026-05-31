"""Entrypoint de FastAPI.

Levanta la app, registra middlewares y monta routers de la API v1.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import auth, chat, health
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

# Campos cuyo valor (``input``) JAMÁS debe ecoarse en un 422 (regla #4). El
# RequestValidationError de Pydantic adjunta el ``input`` que falló; para un
# password corto eso devolvería el password en claro al cliente (y a cualquier
# log que capture la response). Se scrubea por nombre de campo, no por ruta: es
# defensa en profundidad y aplica a cualquier endpoint que reciba estos campos.
_SENSITIVE_VALIDATION_FIELDS = frozenset({"password", "password_hash"})
_VALIDATION_SCRUBBED = "[scrubbed]"


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Devuelve el 422 de validación scrubbeando el eco de campos sensibles.

    Replica el shape default de FastAPI (``{"detail": [...]}``) pero reemplaza el
    ``input`` (y un ``ctx`` que pudiera copiarlo) de cualquier error cuyo último
    segmento de ``loc`` sea un campo sensible (``password`` / ``password_hash``).
    Así un password corto da 422 sin filtrar el valor enviado (regla #4).
    """
    scrubbed: list[dict[str, Any]] = []
    for error in exc.errors():
        item = dict(error)
        loc = item.get("loc") or ()
        if loc and loc[-1] in _SENSITIVE_VALIDATION_FIELDS:
            if "input" in item:
                item["input"] = _VALIDATION_SCRUBBED
            # ``ctx`` puede contener el valor o un objeto no serializable; lo
            # dropeamos para no reintroducir el eco ni romper la serialización.
            item.pop("ctx", None)
        scrubbed.append(item)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": scrubbed},
    )


app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(auth.router, prefix="/v1", tags=["auth"])
app.include_router(chat.router, prefix="/v1", tags=["chat"])

# TODO: agregar routers de memory, sessions cuando estén.
