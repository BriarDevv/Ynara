"""Dependencias compartidas de FastAPI.

Sesión de DB async, usuario actual a partir de JWT, etc.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Engine async (Postgres con asyncpg). Se asume que `database_url` viene
# en formato sync (postgresql://...); para SQLAlchemy async hace falta
# `postgresql+asyncpg://...`. Convertimos si hace falta.
_url = settings.database_url
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _url,
    pool_size=settings.database_pool_size,
    pool_pre_ping=True,
    echo=False,
)

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
