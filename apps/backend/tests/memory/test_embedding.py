"""Test de ``app/memory/embedding.embed_one``: embeddea UN texto y devuelve su vector.

Lockea el contrato que antes vivía duplicado como ``_embed_one`` en los stores
semántico/episódico: ``embed_one(embedder, text) == embedder.embed([text])[0]``.
"""

from __future__ import annotations

from app.llm.clients.embedding import FakeEmbeddingClient
from app.memory.embedding import embed_one


async def test_embed_one_returns_first_vector() -> None:
    embedder = FakeEmbeddingClient()
    text = "un hecho cualquiera"
    out = await embed_one(embedder, text)
    # Es exactamente el primer (único) vector de embed([text]).
    expected = (await embedder.embed([text]))[0]
    assert out == expected
    assert isinstance(out, list)
    assert out and all(isinstance(x, float) for x in out)
