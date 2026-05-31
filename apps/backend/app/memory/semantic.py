"""Storage propio cifrado para la capa de memoria semántica (engine in-house,
ADR-010, supersede ADR-003).

Hechos persistentes sobre el usuario en la tabla sagrada ``semantic_memory``.
El ``content`` vive cifrado AES-256-GCM (``BYTEA``) vía ``app/core/crypto.py``;
el ``content_embedding`` (``Vector(1024)``) va en claro para habilitar la
búsqueda ANN. **Nada de Mem0**: storage hand-rolled sobre Postgres + pgvector
(ADR-010 D1).

Pipeline (ADR-010 D2):

- **Write** (``add`` / ``update``): se embeddea el **plaintext** primero, después
  se cifra con ``encrypt_for_user`` y recién se persiste el blob. El ``Out`` se
  devuelve con el ``content`` plaintext original (nunca el ``BYTEA``).
- **Read** (``search``): ``embed(query)`` → ANN HNSW cosine top-K filtrado por
  ``user_id`` → **descifrar el top-K in-process** → rerank passthrough
  (``FakeReranker`` en M7) → recortar a ``limit`` → construir los ``Out``.

El descifrado va **siempre antes** de construir ``SemanticMemoryOut``: el schema
es ``strict=True`` y rechaza el ``BYTEA`` crudo con ``ValidationError`` (defensa
en profundidad).

``SemanticMemoryStore`` se construye **por request** ligando ``user_id`` en el
``__init__``: la key de cifrado se deriva de ``user_id`` (``crypto.py``), así que
un ``user_id`` por-llamada permitiría descifrar el blob de otro usuario. Ligarlo
en el constructor vuelve el aislamiento estructural (regla #3 / ADR-010).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user, encrypt_for_user
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.models.memory import SemanticMemory
from app.schemas.memory import SemanticMemoryCreate, SemanticMemoryOut

# Tamaño del top-K que el ANN trae antes de descifrar + rerankear (ADR-010 D2).
# El rerank (passthrough en M7) reordena estos candidatos y luego se recorta a
# ``limit``. Holgura sobre ``limit`` para que el reranker tenga material.
_ANN_TOP_K = 50


class SemanticMemoryStore:
    """Store por-request de la capa semántica, ligado a un ``user_id``.

    El ``user_id`` se liga en el constructor (deriva la key de cifrado): todo
    query filtra por ``self._user_id`` y todo descifrado usa esa misma identidad.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        embedder: EmbeddingClient,
        reranker: Reranker,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._embedder = embedder
        self._reranker = reranker

    async def _embed_one(self, text: str) -> list[float]:
        """Embeddea un solo texto plaintext. Devuelve el vector de 1024 floats."""
        vectors = await self._embedder.embed([text])
        return vectors[0]

    async def add(self, payload: SemanticMemoryCreate) -> SemanticMemoryOut:
        """Persiste un hecho semántico: embeddea el plaintext, lo cifra, INSERTA.

        Devuelve el ``Out`` con el ``content`` **plaintext** original (no el blob).
        """
        embedding = await self._embed_one(payload.content)
        blob = encrypt_for_user(self._user_id, payload.content)

        row = SemanticMemory(
            user_id=self._user_id,
            content=blob,
            content_embedding=embedding,
            importance=payload.importance,
            source_session_id=payload.source_session_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_out(row, plaintext=payload.content)

    async def search(self, query: str, limit: int = 5) -> list[SemanticMemoryOut]:
        """Búsqueda semántica: ANN top-K → descifrar → rerank → recortar a ``limit``.

        Solo devuelve filas del usuario del store, con ``content`` descifrado.
        """
        if limit <= 0:
            return []

        qvec = await self._embed_one(query)
        stmt = (
            select(SemanticMemory)
            .where(SemanticMemory.user_id == self._user_id)
            .order_by(SemanticMemory.content_embedding.cosine_distance(qvec))
            .limit(_ANN_TOP_K)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        if not rows:
            return []

        # Descifrar el top-K in-process ANTES de tocar el schema strict.
        plaintexts = [decrypt_for_user(self._user_id, row.content) for row in rows]

        # Rerank passthrough (FakeReranker en M7): preserva el orden ANN.
        ranked = await self._reranker.rerank(query, plaintexts, top_n=limit)
        return [self._to_out(rows[r.index], plaintext=plaintexts[r.index]) for r in ranked]

    async def list_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> list[SemanticMemoryOut]:
        """Lista los hechos del usuario sin búsqueda: ``created_at`` DESC, paginado.

        Read-only para el dueño (``GET /v1/memory``). Filtra por ``self._user_id``
        (aislamiento estructural, igual que ``search``), trae la página
        ``[offset, offset+limit)`` ordenada por ``created_at`` DESC y descifra el
        ``content`` fila por fila con ``decrypt_for_user`` ANTES de construir el
        ``Out`` strict. NO embeddea (no hay query): es un listado, no una búsqueda.

        ``limit=None`` (default) trae TODAS las filas del usuario en un solo query
        (lo usa ``GET /v1/memory/export``, que no pagina): evita el ``count()``
        como límite y su TOCTOU (una fila escrita por el worker entre el ``count``
        y el ``select`` se perdería del export).
        """
        stmt = (
            select(SemanticMemory)
            .where(SemanticMemory.user_id == self._user_id)
            .order_by(SemanticMemory.created_at.desc())
            .offset(offset)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await self._session.execute(stmt)).scalars().all())
        # Descifrar fila por fila ANTES del schema strict (todas son del user).
        return [
            self._to_out(row, plaintext=decrypt_for_user(self._user_id, row.content))
            for row in rows
        ]

    async def count(self) -> int:
        """Cuenta los hechos del usuario (``total`` de la paginación). No descifra."""
        stmt = (
            select(func.count())
            .select_from(SemanticMemory)
            .where(SemanticMemory.user_id == self._user_id)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def get_by_id(self, memory_id: UUID) -> SemanticMemoryOut | None:
        """Lee un hecho por ``id`` del usuario del store. ``None`` si no es suyo.

        DISCIPLINA DECRYPT-POST-OWNERSHIP: el WHERE filtra por ``id`` **y**
        ``user_id``; si la fila no existe o pertenece a otro usuario, el query
        devuelve ``None`` y se retorna ``None`` ANTES de tocar crypto. NUNCA se
        invoca ``decrypt_for_user`` sobre el blob de otro usuario (descifrar con la
        key derivada de ``self._user_id`` el blob ajeno tiraría ``InvalidTag``, pero
        ni siquiera se intenta: ajena == inexistente). Solo si la fila es del user
        se descifra y se construye el ``Out``.
        """
        stmt = select(SemanticMemory).where(
            SemanticMemory.id == memory_id,
            SemanticMemory.user_id == self._user_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            # Inexistente o ajena: se retorna None ANTES de descifrar nada.
            return None
        # Recién acá, confirmada la propiedad, se descifra.
        plaintext = decrypt_for_user(self._user_id, row.content)
        return self._to_out(row, plaintext=plaintext)

    async def update(self, memory_id: UUID, content: str) -> SemanticMemoryOut | None:
        """Re-embeddea + re-cifra y actualiza el hecho.

        Filtra por ``id`` **y** ``user_id``: ``None`` si no existe o pertenece a
        otro usuario (sin filtrar de más, no se descifra nada ajeno).
        """
        embedding = await self._embed_one(content)
        blob = encrypt_for_user(self._user_id, content)

        stmt = (
            sa_update(SemanticMemory)
            .where(
                SemanticMemory.id == memory_id,
                SemanticMemory.user_id == self._user_id,
            )
            .values(content=blob, content_embedding=embedding)
            .returning(SemanticMemory)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.flush()
        if row is None:
            return None
        return self._to_out(row, plaintext=content)

    async def delete(self, memory_id: UUID) -> bool:
        """Borra físicamente un hecho. ``True`` si borró una fila del usuario."""
        stmt = (
            sa_delete(SemanticMemory)
            .where(
                SemanticMemory.id == memory_id,
                SemanticMemory.user_id == self._user_id,
            )
            .returning(SemanticMemory.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_out(row: SemanticMemory, *, plaintext: str) -> SemanticMemoryOut:
        """Construye el ``Out`` con el ``content`` ya descifrado (nunca el ``BYTEA``)."""
        return SemanticMemoryOut(
            id=row.id,
            user_id=row.user_id,
            content=plaintext,
            importance=row.importance,
            source_session_id=row.source_session_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
