"""Storage propio cifrado para la capa de memoria episódica (engine in-house,
ADR-010).

Resúmenes de sesiones pasadas en la tabla sagrada ``episodic_memory``. El
``summary`` vive cifrado AES-256-GCM (``BYTEA``) vía ``app/core/crypto.py``; el
``summary_embedding`` (``Vector(1024)``) va en claro para la búsqueda ANN. Las
entradas las genera el worker de Celery al cerrar una sesión (Qwen resume,
calcula el embedding); aquí solo se persiste y se busca.

Pipeline idéntico al semántico (ADR-010 D2): write embeddea el **plaintext**,
cifra, persiste; read hace ANN top-K → descifrar in-process → rerank passthrough
→ recortar a ``limit``. El descifrado va **siempre antes** de construir
``EpisodicMemoryOut`` (schema ``strict=True``, rechaza ``BYTEA`` crudo).

Los campos ``is_sensitive`` / ``retention_days`` / ``topics`` / ``session_id`` /
``occurred_at`` se persisten **tal como llegan** en ``EpisodicMemoryCreate``: ya
fueron validados por el ``model_validator`` del schema (cap de retención sensible,
ADR-007 D2) y por las CHECK constraints del modelo. El store **no** re-chequea.

``EpisodicMemoryStore`` se construye **por request** ligando ``user_id`` en el
``__init__`` (la key de cifrado se deriva de ``user_id``): aislamiento estructural
(regla #3 / ADR-010).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user, encrypt_for_user
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.models.memory import EpisodicMemory
from app.schemas.memory import EpisodicMemoryCreate, EpisodicMemoryOut

# Top-K del ANN antes de descifrar + rerankear (ver semantic.py / ADR-010 D2).
_ANN_TOP_K = 50


class EpisodicMemoryStore:
    """Store por-request de la capa episódica, ligado a un ``user_id``."""

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

    async def add(self, payload: EpisodicMemoryCreate) -> EpisodicMemoryOut:
        """Persiste un resumen episódico: embeddea el plaintext, lo cifra, INSERTA.

        ``is_sensitive`` / ``retention_days`` / ``topics`` / ``session_id`` /
        ``occurred_at`` se escriben tal como llegan (ya validados por el schema).
        Devuelve el ``Out`` con el ``summary`` **plaintext** original.
        """
        embedding = await self._embed_one(payload.summary)
        blob = encrypt_for_user(self._user_id, payload.summary)

        row = EpisodicMemory(
            user_id=self._user_id,
            session_id=payload.session_id,
            summary=blob,
            summary_embedding=embedding,
            is_sensitive=payload.is_sensitive,
            retention_days=payload.retention_days,
            occurred_at=payload.occurred_at,
            topics=payload.topics,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_out(row, plaintext=payload.summary)

    async def search(self, query: str, limit: int = 5) -> list[EpisodicMemoryOut]:
        """Búsqueda episódica: ANN top-K → descifrar → rerank → recortar a ``limit``.

        Solo devuelve filas del usuario del store, con ``summary`` descifrado.
        """
        if limit <= 0:
            return []

        qvec = await self._embed_one(query)
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.user_id == self._user_id)
            .order_by(EpisodicMemory.summary_embedding.cosine_distance(qvec))
            .limit(_ANN_TOP_K)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        if not rows:
            return []

        # Descifrar el top-K in-process ANTES de tocar el schema strict.
        plaintexts = [decrypt_for_user(self._user_id, row.summary) for row in rows]

        # Rerank passthrough (FakeReranker en M7): preserva el orden ANN.
        ranked = await self._reranker.rerank(query, plaintexts, top_n=limit)
        return [self._to_out(rows[r.index], plaintext=plaintexts[r.index]) for r in ranked]

    @staticmethod
    def _to_out(row: EpisodicMemory, *, plaintext: str) -> EpisodicMemoryOut:
        """Construye el ``Out`` con el ``summary`` ya descifrado (nunca el ``BYTEA``)."""
        return EpisodicMemoryOut(
            id=row.id,
            user_id=row.user_id,
            session_id=row.session_id,
            summary=plaintext,
            is_sensitive=row.is_sensitive,
            retention_days=row.retention_days,
            occurred_at=row.occurred_at,
            topics=row.topics,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
