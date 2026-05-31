"""Dependencias compartidas de FastAPI.

Sesión de DB async, usuario actual a partir de JWT, clientes LLM/embedder/
reranker leídos desde ``app.state`` (singletons construidos en el lifespan).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import InvalidTokenError, verify_access_token
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker

settings = get_settings()

# Engine async (Postgres con asyncpg). `database_url` puede venir en formato
# sync (`postgresql://...`); SQLAlchemy async necesita `postgresql+asyncpg://`.
_url = settings.database_url
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Compatibilidad con los poolers de Supabase (pgbouncer): el transaction
# pooler (puerto 6543) no soporta prepared statements, que asyncpg cachea por
# default -> los desactivamos siempre (inocuo para el session pooler 5432 y la
# conexion directa). Con el transaction pooler ademas conviene NullPool: el
# pooling lo hace pgbouncer, SQLAlchemy no debe retener conexiones.
_is_transaction_pooler = urlsplit(_url).port == 6543
_engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
    "echo": False,
    "connect_args": {"statement_cache_size": 0},
}
if _is_transaction_pooler:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = settings.database_pool_size

engine = create_async_engine(_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield de AsyncSession para inyección en endpoints."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=True)


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
) -> UUID:
    """Extrae el user_id UUID del JWT. Pura, sin hit a DB.

    Levanta HTTP 401 si el token es inválido, expirado o el ``sub`` no es un UUID.
    El header ``WWW-Authenticate: Bearer`` se incluye según el RFC 6750.
    """
    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_access_token(token)
    except InvalidTokenError as exc:
        raise _unauthorized from exc
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _unauthorized from exc


CurrentUser = Annotated[UUID, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Clientes LLM / embedder / reranker — singletons del lifespan (app.state)
# ---------------------------------------------------------------------------
# El lifespan de app/main.py construye los singletons una vez en startup.
# Cuando vLLM esté disponible, solo cambia el lifespan; estas deps no tocan.


def get_llm_client(request: Request) -> LLMClient:
    """Devuelve el cliente LLM singleton construido en el lifespan."""
    return request.app.state.llm_client  # type: ignore[no-any-return]


def get_embedder(request: Request) -> EmbeddingClient:
    """Devuelve el cliente de embeddings singleton construido en el lifespan."""
    return request.app.state.embedder  # type: ignore[no-any-return]


def get_reranker(request: Request) -> Reranker:
    """Devuelve el cliente de reranking singleton construido en el lifespan."""
    return request.app.state.reranker  # type: ignore[no-any-return]
