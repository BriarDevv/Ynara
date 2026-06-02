"""Entrypoint de FastAPI.

Levanta la app, registra middlewares y monta routers de la API v1.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.api.v1 import auth, chat, health, memory, sessions
from app.core.config import get_settings
from app.core.db_guard import guard_against_prod_db_in_dev
from app.core.observability import init_sentry
from app.core.token_store import RedisTokenStore
from app.llm.clients.factory import build_llm_clients
from app.llm.config import load_llm_config

settings = get_settings()

# Error tracking: no-op si no hay SENTRY_DSN. Antes de crear la app para
# capturar errores de startup. El before_send limpia PII (regla #4).
init_sentry()

# Headers de seguridad base que aplican a TODA respuesta, en cualquier
# environment. Valores fijos (no dependen de settings):
#   - X-Content-Type-Options: nosniff  -> el browser no adivina el MIME type.
#   - X-Frame-Options: DENY            -> no se puede embeber en un <iframe>.
#   - Referrer-Policy: no-referrer     -> nunca se filtra la URL de origen.
_BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
# HSTS: fuerza HTTPS por 1 año (incluyendo subdominios). SOLO en production:
# en dev/local se sirve por HTTP y un HSTS cacheado rompería el acceso local.
_HSTS_HEADER_VALUE = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Middleware ASGI puro: inyecta los headers de seguridad en TODA respuesta.

    Implementado como ASGI puro (envuelve ``send`` y agrega los headers en el
    mensaje ``http.response.start``) en vez de ``BaseHTTPMiddleware`` a propósito:
    (1) no bufferea el body, así NO rompe el stream SSE de ``/chat/stream``;
    (2) cubre cualquier respuesta normal (2xx-4xx, incluidos 401/404/409/422/429).

    Los 3 headers base van siempre; ``Strict-Transport-Security`` solo cuando
    ``settings.environment == "production"``. El environment se lee en cada request
    (módulo-global ``settings``) para que los tests lo parcheen sin recrear la app.

    Limitación conocida y ACEPTADA: un 500 NO MANEJADO lo genera el
    ``ServerErrorMiddleware`` de Starlette, que está POR FUERA de los
    user-middlewares (este incluido), así que ese 500 crudo NO lleva estos headers.
    Se acepta el gap porque (a) un 500 es un JSON genérico sin contenido del usuario
    sniffable/embebible, y (b) cubrirlo exigiría envolver por fuera del
    ``ServerErrorMiddleware`` o un handler de ``Exception`` que podría interferir con
    la captura de Sentry (``before_send``, regla #4) — riesgo que no compensa el bajo
    impacto de unos headers sobre un 500 genérico.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for header, value in _BASE_SECURITY_HEADERS.items():
                    headers[header] = value
                if settings.environment == "production":
                    headers["Strict-Transport-Security"] = _HSTS_HEADER_VALUE
            await send(message)

        await self.app(scope, receive, send_with_headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de startup/shutdown.

    Construye los clientes LLM/embedder/reranker como singletons en
    ``app.state`` para que las deps de FastAPI los inyecten sin recrearlos
    por request.  La ``factory`` decide Fakes (dev/test, default) vs. clientes
    reales (``ResilientClient(build_pool(VllmClient...))`` en production); los
    *served_name* salen del config (p.ej. 'qwen', 'gemma4'), NO las keys del
    dict de modelos.

    TODO: warm-up del LLM router, etc.

    Redis (issue #63): se construye UN solo cliente ``app.state.redis`` acá
    (reusable, cerrado en shutdown) y se envuelve en el ``RedisTokenStore``
    (``app.state.token_store``) que la blocklist + rate-limit consumen vía deps.
    ``health.check_redis`` reusa este mismo cliente (no abre uno por probe).
    """
    # Guard anti-prod (PRIMERA línea): si NO es producción y el DATABASE_URL
    # apunta a una DB de prod conocida (Supabase) sin opt-in explícito, abortar
    # el arranque ANTES de construir cualquier cliente o tocar la DB. No se
    # dispara en production, con YNARA_ALLOW_PROD_DB=1, ni bajo pytest.
    guard_against_prod_db_in_dev(
        environment=settings.environment,
        database_url=settings.database_url,
    )

    # startup — clientes como singletons. La factory gatea Fakes (dev/test) vs.
    # ResilientClient/VllmClient reales (production); el resto del stack no cambia.
    cfg = load_llm_config()
    (
        app.state.llm_client,
        app.state.embedder,
        app.state.reranker,
    ) = build_llm_clients(settings, cfg)

    # Redis singleton + token store (blocklist + rate-limit, issue #63). UN solo
    # cliente para toda la app: lo reusan las deps de auth y health.check_redis.
    app.state.redis = aioredis.from_url(settings.redis_url)
    app.state.token_store = RedisTokenStore(app.state.redis)

    yield

    # shutdown — liberar recursos. El llm_client puede ser un ResilientClient REAL
    # (un httpx.AsyncClient por instancia vLLM) en production; aclose() cierra esos
    # connection pools (en dev/test es el no-op del Fake), evitando fuga de sockets.
    # embedder/reranker hoy son Fakes sin recursos; cuando tengan cliente real,
    # cerrarlos acá también. Redis se cierra siempre.
    await app.state.llm_client.aclose()
    await app.state.redis.aclose()


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

# Security headers en cada respuesta normal (ver gap de 500-crudo en el docstring
# del middleware). CORS se agrega antes y sigue intacto: Starlette ejecuta los
# middlewares en orden inverso al de registro, así que este queda "por dentro" del
# de CORS y ninguno pisa los headers del otro.
app.add_middleware(SecurityHeadersMiddleware)

# Campos cuyo valor (``input``) JAMÁS debe ecoarse en un 422 (regla #4). El
# RequestValidationError de Pydantic adjunta el ``input`` que falló; para un
# password corto eso devolvería el password en claro al cliente (y a cualquier
# log que capture la response). Se scrubea por nombre de campo, no por ruta: es
# defensa en profundidad y aplica a cualquier endpoint que reciba estos campos.
# Issue #63: ``refresh_token`` / ``access_token`` se agregan para que un 422
# sobre /auth/refresh|logout no ecoe el token crudo (regla #4).
_SENSITIVE_VALIDATION_FIELDS = frozenset(
    {"password", "password_hash", "refresh_token", "access_token"}
)
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
app.include_router(sessions.router, prefix="/v1", tags=["sessions"])
app.include_router(memory.router, prefix="/v1", tags=["memory"])
