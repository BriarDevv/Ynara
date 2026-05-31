"""Task Celery de consolidacion de memoria semantica + procedural (M8 Ola 2).

Reglas no negociables (ADR-010 + critica adversarial M8):

1. Solo encolada cuando el modelo del modo escribe memoria (Qwen). El caller
   (``_run_chat_turn`` en el endpoint) ya filtra; esta task no re-chequea.
2. La task NUNCA esta en el path de respuesta: ``_run_chat_turn`` encola con
   ``.delay()`` DESPUES del commit (M10 Ola 0); la escritura ocurre aqui,
   en el worker Celery, de forma async.
3. NUNCA episodica: ``layer`` = ``semantic`` | ``procedural`` solamente.
   NUNCA ``source_session_id`` (el ``session_id`` de Ola 2 es OPACO, no es
   una FK real de ``sessions.id``).
4. Serializacion 100% JSON: la firma de la task es solo strings/primitivos.
   El worker RECONSTRUYE todas sus deps in-process desde ``get_settings()``.
   El engine de DB usa ``NullPool`` obligatorio (sin el, reusar conexiones
   entre event loops distintos da 'Future attached to a different loop').
5. Parseo defensivo heredado de ``QwenMemoryEngine._parse_ops``: JSON
   invalido / ops malformadas -> [] sin crashear el worker.
6. Ningun dato de usuario a logs (regla #4): el payload (turno del usuario)
   queda on-prem en Redis/worker. Solo se loguea el conteo de ops aplicadas
   y errores tecnicos SIN contenido.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient, FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker, Reranker
from app.llm.memory_engine import QwenMemoryEngine, apply_ops
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de construccion de deps (inyectables en tests)
# ---------------------------------------------------------------------------


def _normalize_db_url(url: str) -> str:
    """Normaliza la URL de DB a dialect asyncpg."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _build_embedder(settings: Settings) -> EmbeddingClient:
    """Construye el cliente de embeddings segun ``embedding_backend``.

    En M8 el backend operativo puede ser 'fake' (sin GPU). El branch 'vllm'
    queda con un TODO para cuando el servidor de bge-m3 este disponible.
    """
    if settings.embedding_backend == "vllm":
        # TODO (Ola 3+): instanciar VllmEmbeddingClient(base_url=settings.embedding_base_url)
        # cuando el servidor de embeddings este disponible (ADR-009).
        # Por ahora caemos al fake tambien en este branch.
        return FakeEmbeddingClient()
    # 'fake' (default operativo en M8)
    return FakeEmbeddingClient()


def _build_consolidation_llm(settings: Settings) -> FakeLlmClient:
    """Construye el cliente LLM para consolidacion (Qwen).

    En M8 Ola 2 el cliente real (VllmClient contra el endpoint de Qwen) no
    esta conectado aqui: la task de consolidacion usa el mismo FakeLlmClient
    que el test (para M8). El cliente real se conecta cuando el endpoint de
    consolidacion se exponga en Ola 3+ (ADR-009 D4).

    TODO (Ola 3+): instanciar VllmClient(base_url=settings.llm_secondary_base_url)
    o reusar el ResilientClient del pool cuando el pool sea inyectable en el
    worker Celery.
    """
    # Served models vacio: en prod este LLM lo provee el caller via inyeccion
    # (tests) o el pool real (futuro). Para el worker Celery real en M8 el
    # QwenMemoryEngine con un FakeLlmClient devolvera [] (sin resultados
    # encolados), lo que es el comportamiento correcto: la task aplica 0 ops
    # y commitea sin efectos secundarios.
    return FakeLlmClient(served_models=frozenset({"qwen"}))


def _build_reranker() -> Reranker:
    """Construye el reranker para consolidacion.

    FakeReranker passthrough en M8. El reranker real (cross-encoder) se
    conecta en un milestone separado gateado por disponibilidad de GPU.
    TODO (Ola 3+): instanciar VllmRerankerClient cuando este disponible.
    """
    return FakeReranker()


# ---------------------------------------------------------------------------
# Cuerpo async de la consolidacion (separado para inyeccion en tests)
# ---------------------------------------------------------------------------


async def _async_consolidate(
    *,
    user_id: str,
    session_id: str,  # OPACO: no se usa como FK
    user_msg: str,
    model_response: str,
    mode: str,
    # Inyectables para tests (None => construir desde get_settings())
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    embedder: EmbeddingClient | None = None,
    reranker: Reranker | None = None,
    # session inyectable para tests de integracion (evita crear engine nuevo)
    session: AsyncSession | None = None,
) -> int:
    """Nucleo async de la consolidacion; retorna la cantidad de ops aplicadas.

    Si ``session`` se inyecta (tests de integracion), se usa directamente y
    NO se crea engine ni se hace commit (el fixture del test controla el
    ciclo de vida de la sesion). Si es ``None`` (worker Celery en prod), se
    construye el engine con ``NullPool`` (decision #4 M8), se abre la sesion,
    se commitea y se dispone el engine.

    ``session_id`` es opaco: NO se pasa como ``source_session_id`` a ningun
    store (decision #3 M8, ADR-010).
    """
    cfg = settings or get_settings()

    # --- Dependencias inyectadas o construidas ---
    effective_llm = llm_client or _build_consolidation_llm(cfg)
    effective_embedder = embedder or _build_embedder(cfg)
    effective_reranker = reranker or _build_reranker()

    uid = UUID(user_id)
    engine = None

    try:
        if session is not None:
            # Modo test: usar la sesion inyectada, no crear engine.
            sem_store = SemanticMemoryStore(session, uid, effective_embedder, effective_reranker)
            proc_store = ProceduralMemoryStore(session, uid)

            mem_engine = QwenMemoryEngine(effective_llm)
            ops = await mem_engine.consolidate(
                user_msg=user_msg,
                model_response=model_response,
                mode=mode,
            )
            applied = await apply_ops(ops, semantic_store=sem_store, procedural_store=proc_store)
            # NO commitear aqui: el fixture controla el rollback.
            return applied

        # Modo produccion: construir engine con NullPool (decision #4).
        db_url = _normalize_db_url(cfg.database_url)
        engine = create_async_engine(db_url, poolclass=NullPool)
        maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with maker() as db_session:
            sem_store = SemanticMemoryStore(
                db_session, uid, effective_embedder, effective_reranker
            )
            proc_store = ProceduralMemoryStore(db_session, uid)

            mem_engine = QwenMemoryEngine(effective_llm)
            ops = await mem_engine.consolidate(
                user_msg=user_msg,
                model_response=model_response,
                mode=mode,
            )
            applied = await apply_ops(ops, semantic_store=sem_store, procedural_store=proc_store)
            await db_session.commit()

        return applied

    finally:
        if engine is not None:
            await engine.dispose()


# ---------------------------------------------------------------------------
# Task Celery — firma 100% JSON-serializable
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="workflows.consolidate_turn")
def consolidate_turn(
    self,  # bind=True, self no se usa (sin retry manual en M8)
    *,
    user_id: str,
    session_id: str,
    user_msg: str,
    model_response: str,
    mode: str,
) -> None:
    """Task Celery: consolida el turno del usuario en memoria semantica + procedural.

    Firma 100% strings/primitivos (``task_serializer='json'``). NUNCA cruza
    el wire un ``AsyncSession``, un ``LLMClient``, un ``UUID`` ni un store.

    El cuerpo async se corre con ``asyncio.run`` (worker prefork de Celery).
    Todo el bloque se envuelve en ``try/except``: un fallo NO tumba el worker
    (loguea un mensaje SIN el contenido del usuario, regla #4).

    Args:
        user_id: UUID del usuario como string (JSON-safe).
        session_id: ID de sesion OPACO como string (NO es FK; no se usa como
            ``source_session_id`` en ningun store).
        user_msg: Mensaje del usuario (on-prem, NO se loguea).
        model_response: Respuesta del modelo (on-prem, NO se loguea).
        mode: Modo activo de la sesion (p.ej. 'vida', 'estudio').
    """
    try:
        applied = asyncio.run(
            _async_consolidate(
                user_id=user_id,
                session_id=session_id,
                user_msg=user_msg,
                model_response=model_response,
                mode=mode,
            )
        )
        logger.info(
            "consolidate_turn: user=%s session=%s applied=%d",
            user_id,
            session_id,
            applied,
        )
    except Exception:
        # Regla: el worker NUNCA muere por un fallo de consolidacion.
        # Log tecnico sin datos de usuario (regla #4).
        logger.exception(
            "consolidate_turn: fallo al consolidar user=%s session=%s (sin datos de usuario)",
            user_id,
            session_id,
        )
