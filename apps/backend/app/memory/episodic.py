"""Memoria episódica: resúmenes de sesiones pasadas.

Se genera al cerrar una sesión (vía worker Celery): Qwen resume la
sesión, calcula embedding del resumen, persiste con metadata (modo,
duración, tópicos).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID


async def add(
    user_id: UUID,
    session_id: UUID,
    summary: str,
    occurred_at: datetime,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """Persiste un resumen episódico."""
    raise NotImplementedError("episodic.add TODO")


async def search(
    user_id: UUID,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Búsqueda episódica por similitud del resumen."""
    raise NotImplementedError("episodic.search TODO")
