"""Helper de construcción del triplete de stores de memoria para /v1/memory.

``build_memory_stores`` arma de una sola vez los tres stores por-request
(semantic / episodic / procedural) ligados al ``user_id`` del JWT. Varios
endpoints del router (``list_memory`` / ``export_memory`` / ``wipe_memory``)
necesitan las TRES capas juntas y reconstruían el triplete idéntico cada uno
(DRY: centralizarlo evita el drift entre call sites).

El ``__init__`` de los stores SAGRADOS (``app/memory/``) NO se toca: este helper
solo orquesta su construcción tal cual (semantic/episodic toman embedder +
reranker; procedural no, no cifra ni embeddea). El embedder/reranker viajan
aunque el listado/export/wipe no embeddeen: es lo menos invasivo, no se altera la
firma sagrada.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore


def build_memory_stores(
    session: AsyncSession,
    user_id: UUID,
    *,
    embedder: EmbeddingClient,
    reranker: Reranker,
) -> tuple[SemanticMemoryStore, EpisodicMemoryStore, ProceduralMemoryStore]:
    """Construye el triplete de stores por-request ligados al ``user_id``.

    Devuelve ``(semantic, episodic, procedural)`` en ese orden. El procedural no
    recibe embedder/reranker (no cifra ni embeddea); el resto sí, espejando el
    ``__init__`` de cada store sagrado sin modificarlo.
    """
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)
    return semantic, episodic, procedural
