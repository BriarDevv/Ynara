"""Helper compartido de embedding para los stores de memoria (semántica/episódica).

Función pura sin estado: embeddea UN texto y devuelve su vector de 1024 floats.
Antes vivía duplicada como ``_embed_one`` idéntico en ``semantic.py`` y
``episodic.py``; acá queda en un solo lugar. El cifrado va DESPUÉS (ADR-010 D2:
se embeddea el plaintext y recién se cifra), así que este helper opera sobre
texto en claro.
"""

from __future__ import annotations

from app.llm.clients.embedding import EmbeddingClient


async def embed_one(embedder: EmbeddingClient, text: str) -> list[float]:
    """Embeddea un solo texto plaintext. Devuelve el vector de 1024 floats."""
    vectors = await embedder.embed([text])
    return vectors[0]
