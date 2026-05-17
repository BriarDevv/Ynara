"""Memoria procedural: preferencias y patrones del usuario.

JSONB estructurado, sin embeddings. Lookup directo por key.
Las entradas pueden tener un ``confidence`` (0-1) que decae si el
patrón deja de observarse.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


async def upsert(user_id: UUID, key: str, value: dict[str, Any], confidence: float = 1.0) -> None:
    """Inserta o actualiza una entrada procedural por key."""
    raise NotImplementedError("procedural.upsert TODO")


async def get(user_id: UUID, key: str) -> dict[str, Any] | None:
    """Lee una entrada procedural por key."""
    raise NotImplementedError("procedural.get TODO")


async def list_all(user_id: UUID) -> list[dict[str, Any]]:
    """Lista todas las entradas procedurales del usuario."""
    raise NotImplementedError("procedural.list_all TODO")


async def delete(user_id: UUID, key: str) -> None:
    """Borra físicamente una entrada procedural."""
    raise NotImplementedError("procedural.delete TODO")
