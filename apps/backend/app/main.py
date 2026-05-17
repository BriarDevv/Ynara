"""Entrypoint de FastAPI.

Levanta la app, registra middlewares y monta routers de la API v1.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import health
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de startup/shutdown.

    TODO: warm-up del LLM router, conexión a Redis, etc.
    """
    # startup
    yield
    # shutdown


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

# TODO: agregar routers de auth, chat, memory, sessions cuando estén.
