"""Dependencias compartidas de FastAPI.

Sesión de DB async, usuario actual a partir de JWT, etc.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

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


# TODO: get_current_user(token: str = Depends(oauth2_scheme)) -> User
