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

import asyncio
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_for_user, decrypt_many_for_user, encrypt_for_user
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.memory.embedding import embed_one
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

    async def add(self, payload: EpisodicMemoryCreate) -> EpisodicMemoryOut:
        """Persiste un resumen episódico: embeddea el plaintext, lo cifra, INSERTA.

        ``is_sensitive`` / ``retention_days`` / ``topics`` / ``session_id`` /
        ``occurred_at`` se escriben tal como llegan (ya validados por el schema).
        Devuelve el ``Out`` con el ``summary`` **plaintext** original.
        """
        embedding = await embed_one(self._embedder, payload.summary)
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

        qvec = await embed_one(self._embedder, query)
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.user_id == self._user_id)
            .order_by(EpisodicMemory.summary_embedding.cosine_distance(qvec))
            .limit(_ANN_TOP_K)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        if not rows:
            return []

        # Descifrar el top-K en un thread (CPU-bound, libera el GIL) ANTES de
        # tocar el schema strict: no bloquea el event loop bajo concurrencia
        # (SCAL-02). Los blobs se materializan en el loop (sin lazy-load en thread).
        blobs = [row.summary for row in rows]
        plaintexts = await asyncio.to_thread(decrypt_many_for_user, self._user_id, blobs)

        # Rerank passthrough (FakeReranker en M7): preserva el orden ANN.
        ranked = await self._reranker.rerank(query, plaintexts, top_n=limit)
        return [self._to_out(rows[r.index], plaintext=plaintexts[r.index]) for r in ranked]

    async def list_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> list[EpisodicMemoryOut]:
        """Lista los episodios del usuario sin búsqueda: ``created_at`` DESC, paginado.

        Read-only para el dueño (``GET /v1/memory``). Filtra por ``self._user_id``
        (aislamiento estructural, igual que ``search``), trae la página
        ``[offset, offset+limit)`` ordenada por ``created_at`` DESC y descifra el
        ``summary`` fila por fila con ``decrypt_for_user`` ANTES de construir el
        ``Out`` strict. NO embeddea (no hay query): es un listado, no una búsqueda.

        ``limit=None`` (default) trae TODAS las filas del usuario en un solo query
        (lo usa ``GET /v1/memory/export``, que no pagina): evita el ``count()``
        como límite y su TOCTOU (una fila escrita por el worker entre el ``count``
        y el ``select`` se perdería del export).
        """
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.user_id == self._user_id)
            .order_by(EpisodicMemory.created_at.desc())
            .offset(offset)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await self._session.execute(stmt)).scalars().all())
        if not rows:
            return []
        # Descifrar el lote en un thread ANTES del schema strict (todas son del
        # user); el export sin tope puede ser grande, no bloquear el loop (SCAL-02).
        blobs = [row.summary for row in rows]
        plaintexts = await asyncio.to_thread(decrypt_many_for_user, self._user_id, blobs)
        return [
            self._to_out(row, plaintext=plaintext)
            for row, plaintext in zip(rows, plaintexts, strict=True)
        ]

    async def count(self) -> int:
        """Cuenta los episodios del usuario (``total`` de la paginación). No descifra."""
        stmt = (
            select(func.count())
            .select_from(EpisodicMemory)
            .where(EpisodicMemory.user_id == self._user_id)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def get_by_id(self, memory_id: UUID) -> EpisodicMemoryOut | None:
        """Lee un episodio por ``id`` del usuario del store. ``None`` si no es suyo.

        DISCIPLINA DECRYPT-POST-OWNERSHIP: el WHERE filtra por ``id`` **y**
        ``user_id``; si la fila no existe o pertenece a otro usuario, el query
        devuelve ``None`` y se retorna ``None`` ANTES de tocar crypto. NUNCA se
        invoca ``decrypt_for_user`` sobre el ``summary`` de otro usuario: ajena ==
        inexistente. Solo si la fila es del user se descifra y se arma el ``Out``.
        """
        stmt = select(EpisodicMemory).where(
            EpisodicMemory.id == memory_id,
            EpisodicMemory.user_id == self._user_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            # Inexistente o ajena: se retorna None ANTES de descifrar nada.
            return None
        # Recién acá, confirmada la propiedad, se descifra.
        plaintext = decrypt_for_user(self._user_id, row.summary)
        return self._to_out(row, plaintext=plaintext)

    async def delete(self, memory_id: UUID) -> bool:
        """Borra físicamente un episodio. ``True`` si borró una fila del usuario.

        Espejo de ``SemanticMemoryStore.delete``: el WHERE filtra por ``id`` **y**
        ``user_id`` (aislamiento estructural). Un id ajeno o inexistente no matchea
        ninguna fila → ``RETURNING id`` vacío → ``False``: NUNCA se borra ni se toca
        el ``summary`` de otro usuario. El dueño puede BORRAR un episodio (no
        reescribirlo: el ``summary`` lo genera el worker de consolidación).
        """
        stmt = (
            sa_delete(EpisodicMemory)
            .where(
                EpisodicMemory.id == memory_id,
                EpisodicMemory.user_id == self._user_id,
            )
            .returning(EpisodicMemory.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none() is not None

    async def wipe(self) -> int:
        """Hard-delete físico de TODOS los episodios del usuario. Devuelve el rowcount.

        Espejo exacto de ``SemanticMemoryStore.wipe``: la primitiva de borrado total de la
        capa episódica para el wipe de cuenta (operación SAGRADA + DESTRUCTIVA + irreversible).
        El ``WHERE`` es ``user_id == self._user_id`` a secas (sin ``id``): barre el estado
        presente COMPLETO de este usuario en ``episodic_memory`` (aislamiento estructural: el
        ``user_id`` se ligó en el ``__init__`` y nunca toca otro usuario).

        NO descifra: borrar el blob ``BYTEA`` del ``summary`` no requiere leerlo en claro, así
        que jamás invoca ``decrypt_for_user`` (regla #4: solo viaja el conteo). Usa
        ``rowcount`` —no ``RETURNING id`` + ``len``— porque es un bulk delete y ningún id se
        usa downstream; el ``rowcount`` es el número REAL de filas borradas (puede diferir de
        un conteo previo si el worker insertó en el ínterin; ese número siempre es verdad).

        Solo hace ``flush``: el ``commit`` lo da el endpoint en el happy path, en la MISMA
        transacción donde recontó (atomicidad recount+wipe+commit).
        """
        stmt = sa_delete(EpisodicMemory).where(EpisodicMemory.user_id == self._user_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

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
