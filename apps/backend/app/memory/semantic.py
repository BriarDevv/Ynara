"""Wrapper sobre Mem0 OSS v2 para la capa de memoria semántica.

Engine: Mem0 OSS v2. Store: Postgres + pgvector. Embedding: bge-m3.

Solo Qwen escribe en esta capa (regla del producto: Gemma solo lee).
La consolidación ocurre **asíncronamente** vía Celery, no en el path
de respuesta.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


async def add(user_id: UUID, content: str, importance: int | None = None) -> UUID:
    """Persiste un hecho semántico.

    TODO: implementar con Mem0. Acá queda la firma esperada.
    """
    raise NotImplementedError("semantic.add TODO")


async def search(
    user_id: UUID,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Búsqueda semántica por similitud."""
    raise NotImplementedError("semantic.search TODO")


async def update(user_id: UUID, memory_id: UUID, content: str) -> None:
    """Actualiza un hecho existente."""
    raise NotImplementedError("semantic.update TODO")


async def delete(user_id: UUID, memory_id: UUID) -> None:
    """Borra físicamente un hecho."""
    raise NotImplementedError("semantic.delete TODO")
