"""Task Celery de consolidacion de memoria semantica + procedural (M8 Ola 2).

Reglas no negociables (ADR-010 + critica adversarial M8):

1. Solo encolada cuando el modelo del modo escribe memoria (Qwen). El caller
   (``ChatService.run_turn`` en el endpoint) ya filtra; esta task no re-chequea.
2. La task NUNCA esta en el path de respuesta: ``ChatService.run_turn`` encola con
   ``.delay()`` DESPUES del commit (M10 Ola 0); la escritura ocurre aqui,
   en el worker Celery, de forma async.
3. NUNCA episodica: ``layer`` = ``semantic`` | ``procedural`` solamente.
   El ``session_id`` ES el ``ChatSession.id`` real (M9 + M10 Ola 0): se parsea
   a ``UUID`` y se propaga como ``source_session_id`` (FK a ``sessions.id``,
   ``ondelete=SET NULL``) en el ADD semantic (M10 Ola 1). El enqueue es
   post-commit (Ola 0), asi que la fila de ``sessions`` ya existe -> sin race FK.
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
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.llm.clients.base import LLMClient
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.factory import build_embedder, build_llm_client, build_reranker
from app.llm.clients.reranker import Reranker
from app.llm.config import load_llm_config
from app.llm.memory_engine import QwenMemoryEngine, apply_ops
from app.memory.audit import AuditStore
from app.memory.config import MemoryConfigError, RetentionConfig, load_retention_config
from app.memory.conversation_turns import ConversationTurnStore
from app.memory.episodic import EpisodicMemoryStore
from app.memory.hashing import compute_record_hash
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.memory import EpisodicMemory
from app.schemas.memory import EpisodicMemoryCreate
from app.workers.celery_app import celery_app
from app.workflows._engine import worker_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de construccion de deps (inyectables en tests)
# ---------------------------------------------------------------------------


def _build_embedder(settings: Settings) -> EmbeddingClient:
    """Construye el cliente de embeddings para la consolidacion.

    Delega en la factory (``build_embedder``): ``embedding_backend='fake'``
    (default sin GPU) -> ``FakeEmbeddingClient``; ``'vllm'`` -> cliente real
    (``VllmEmbeddingClient``, ya implementado; en 16GB apunta a Ollama via su
    API OpenAI-compatible de embeddings, ADR-014). El gate vive en un solo lugar.
    """
    return build_embedder(settings)


def _build_consolidation_llm(settings: Settings) -> LLMClient:
    """Construye el cliente LLM para consolidacion (Qwen).

    Delega en la factory (``build_llm_client``): en dev/test devuelve el
    ``FakeLlmClient`` (sin resultados encolados -> el ``QwenMemoryEngine``
    aplica 0 ops y commitea sin efectos, comportamiento historico de M8); en
    production devuelve el ``ResilientClient`` real contra el servidor
    Ollama/GGUF local (ADR-014; vLLM en 24GB+). El served set sale de
    ``ynara.config.json`` (incluye 'qwen', el modelo de consolidacion).
    """
    return build_llm_client(settings, load_llm_config())


def _build_reranker(settings: Settings) -> Reranker:
    """Construye el reranker para la consolidacion.

    Delega en la factory (``build_reranker``): ``FakeReranker`` passthrough hoy;
    el reranker real (cross-encoder) se gatea en la factory cuando exista.
    """
    return build_reranker(settings)


def _load_retention_config_safe() -> RetentionConfig:
    """Carga la retention de ``ynara.config.json[memory]``, default-safe ante fallo.

    Capa de defensa adicional sobre la regla del modulo: un fallo de config NO
    debe tumbar la consolidacion. Si ``load_retention_config()`` levanta
    ``MemoryConfigError`` (JSON ilegible, valor invalido, key extra), se degrada al
    ``RetentionConfig`` por defaults (=los valores historicos: default=365,
    sensible=180) y se loguea un mensaje tecnico SIN datos de usuario (regla #4: la
    config no es PII, pero igual no se vuelca el detalle del error a logs).
    """
    try:
        return load_retention_config()
    except MemoryConfigError:
        logger.warning(
            "consolidation: ynara.config.json[memory] de retention invalido, "
            "usando defaults ADR-007 D2 (default=365, sensible=180)"
        )
        return RetentionConfig()


def _parse_source_session_id(session_id: str) -> UUID | None:
    """Parsea ``session_id`` (str) a ``UUID`` de forma DEFENSIVA (M10 Ola 1).

    El ``session_id`` que llega al worker es ``str(ChatSession.id)`` (el id real
    de la sesion persistida; ver ``ChatService.run_turn`` en ``app.services.chat``), asi
    que en el camino feliz es siempre un UUID valido. Pero el worker NUNCA debe
    caerse por un payload corrupto en la cola: si el parse falla, se loguea un
    mensaje tecnico SIN contenido del usuario (regla #4 — el ``session_id`` es un
    identificador, no PII) y se devuelve ``None`` para que el hecho se persista
    con ``source_session_id`` NULL en vez de tumbar la consolidacion.

    Returns:
        El ``UUID`` parseado, o ``None`` si ``session_id`` no es un UUID valido.
    """
    try:
        return UUID(session_id)
    except (ValueError, AttributeError, TypeError):
        # session_id corrupto/no-UUID: degradar a None sin crashear el worker.
        # No se loguea el valor (defensa en profundidad sobre regla #4).
        logger.warning("consolidation: session_id no es un UUID valido, source_session_id=None")
        return None


def _parse_origin_mode(mode: str) -> Mode | None:
    """Parsea ``mode`` (str) a ``Mode`` de forma DEFENSIVA (issue #158).

    El ``origin_mode`` de ``audit_log`` es nullable y best-effort: si el ``mode``
    del turno no es un valor valido de ``Mode`` (payload viejo/corrupto en la
    cola), se degrada a ``None`` y la auditoria se escribe igual con
    ``origin_mode=NULL`` en vez de tumbar la consolidacion. NO se loguea el valor
    crudo (defensa en profundidad sobre regla #4: el modo no es PII, pero igual no
    viaja a logs).

    Returns:
        El ``Mode`` parseado, o ``None`` si ``mode`` no es un valor valido.
    """
    try:
        return Mode(mode)
    except ValueError:
        logger.warning("consolidation: mode no es un valor valido de Mode, origin_mode=None")
        return None


# ---------------------------------------------------------------------------
# Cuerpo async de la consolidacion (separado para inyeccion en tests)
# ---------------------------------------------------------------------------


async def _async_consolidate(
    *,
    user_id: str,
    session_id: str,  # str(ChatSession.id): se parsea a UUID y se usa como FK
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

    ``session_id`` es ``str(ChatSession.id)``: el id real de la sesion (FK a
    ``sessions.id``). Se parsea a ``UUID`` de forma DEFENSIVA y se propaga como
    ``source_session_id`` (provenance) a ``apply_ops`` en AMBOS branches (M10
    Ola 1). El enqueue post-commit (M10 Ola 0) garantiza que la ``ChatSession``
    ya este persistida cuando el worker corre, asi que la FK no tiene race. Si
    el parse falla (payload corrupto en la cola), ``source_session_id`` queda
    ``None`` y el hecho se persiste igual (el worker no se cae).
    """
    cfg = settings or get_settings()

    # --- Dependencias inyectadas o construidas ---
    effective_llm = llm_client or _build_consolidation_llm(cfg)
    effective_embedder = embedder or _build_embedder(cfg)
    effective_reranker = reranker or _build_reranker(cfg)

    uid = UUID(user_id)
    # Parse defensivo del session_id: UUID valido -> FK; basura -> None (sin crash).
    source_session_id = _parse_source_session_id(session_id)
    # Parse defensivo del mode -> origin_mode de audit_log (nullable, best-effort).
    origin_mode = _parse_origin_mode(mode)

    if session is not None:
        # Modo test: usar la sesion inyectada, no crear engine ni commitear
        # (el fixture controla el rollback).
        sem_store = SemanticMemoryStore(session, uid, effective_embedder, effective_reranker)
        proc_store = ProceduralMemoryStore(session, uid)
        audit_store = AuditStore(session, uid)

        mem_engine = QwenMemoryEngine(effective_llm)
        ops = await mem_engine.consolidate(
            user_msg=user_msg,
            model_response=model_response,
            mode=mode,
        )
        return await apply_ops(
            ops,
            session=session,
            semantic_store=sem_store,
            procedural_store=proc_store,
            source_session_id=source_session_id,
            audit_store=audit_store,
            origin_model=LlmModel.QWEN,
            origin_mode=origin_mode,
        )

    # Modo produccion: engine NullPool efimero; worker_session commitea al salir
    # del bloque y dispone el engine (decision #4 centralizada en _engine.py).
    async with worker_session(cfg) as db_session:
        sem_store = SemanticMemoryStore(db_session, uid, effective_embedder, effective_reranker)
        proc_store = ProceduralMemoryStore(db_session, uid)
        audit_store = AuditStore(db_session, uid)

        mem_engine = QwenMemoryEngine(effective_llm)
        ops = await mem_engine.consolidate(
            user_msg=user_msg,
            model_response=model_response,
            mode=mode,
        )
        return await apply_ops(
            ops,
            session=db_session,
            semantic_store=sem_store,
            procedural_store=proc_store,
            source_session_id=source_session_id,
            audit_store=audit_store,
            origin_model=LlmModel.QWEN,
            origin_mode=origin_mode,
        )


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
        session_id: ``str(ChatSession.id)`` (id real de la sesion, FK a
            ``sessions.id``). El cuerpo async lo parsea a ``UUID`` de forma
            defensiva y lo propaga como ``source_session_id`` (provenance) en el
            ADD semantic (M10 Ola 1). Si fuera basura no-UUID, degrada a ``None``.
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
    except Exception as exc:
        # Regla: el worker NUNCA muere por un fallo de consolidacion.
        # regla #4: logger.error (NO logger.exception): el traceback / str(exc) podria
        # arrastrar contenido de usuario a los logs. Se loguea solo el TIPO de excepcion.
        logger.error(
            "consolidate_turn: fallo al consolidar user=%s session=%s: %s (sin datos de usuario)",
            user_id,
            session_id,
            type(exc).__name__,
        )


# ===========================================================================
# Consolidacion EPISODICA (issue #209) — al cerrar la sesion
# ===========================================================================
#
# Espejo defensivo de consolidate_turn, pero para la capa episodica:
# - Firma 100% JSON (user_id:str, session_id:str). El cuerpo async se separa en
#   _async_consolidate_session (inyectable en tests).
# - Lee los turnos crudos de la sesion (ConversationTurnStore), los descifra y
#   reconstruye el transcript; si 0 turnos -> 0 (no crea episodio vacio).
# - Idempotencia: si ya existe un episodio para session_id -> no-op (un doble
#   cierre no duplica el episodio). Ademas degrada el IntegrityError de la UNIQUE
#   (session_id) de episodic_memory a no-op (carrera entre dos workers).
# - Resume el transcript con Qwen (QwenMemoryEngine.summarize), persiste via
#   EpisodicMemoryStore.add (embeddea+cifra), audita (AuditStore.record), y purga
#   los turnos. summary+purge son atomicos (mismo commit).
# - is_sensitive = (mode == BIENESTAR); el retention queda capeado por el
#   model_validator de EpisodicMemoryCreate (ADR-007 D2).
# - Regla #4: ningun contenido de usuario a logs (solo conteos / UUIDs /
#   type(exc).__name__).
# ---------------------------------------------------------------------------
#
# RETENTION CONFIG-DRIVEN (ADR-007 D2): los dias de retention (default y
# sensible) salen de ``ynara.config.json[memory]`` via ``load_retention_config()``
# (``app/memory/config.py``), NO de constantes hardcodeadas. Mismo patron que el
# decay config-driven (#211): el ``RetentionConfig`` se inyecta en el cuerpo async
# (``retention_config``) y, si es ``None`` (worker en prod), se carga del JSON. El
# cap duro (<=365) para entradas sensibles lo sigue enforzando el model_validator
# de ``EpisodicMemoryCreate`` + la CHECK constraint. Defaults del loader = los
# valores que estaban hardcodeados aca (default=365, sensible=180): mismo
# comportamiento si el config no trae las keys.
# ---------------------------------------------------------------------------


def _build_transcript(turns: list) -> str:
    """Reconstruye el transcript plaintext de una sesion a partir de los turnos.

    ``turns`` viene ORDER BY ``seq`` y descifrado (``ConversationTurnOut``). Se
    serializa a un texto con prefijos de rol legibles para el modelo. NO se loguea
    (es contenido del usuario, regla #4): solo se pasa al LLM on-prem.
    """
    lines: list[str] = []
    for turn in turns:
        speaker = "Usuario" if turn.role == "user" else "Asistente"
        lines.append(f"{speaker}: {turn.content}")
    return "\n".join(lines)


async def _episode_exists(session: AsyncSession, source_session_id: UUID) -> bool:
    """``True`` si ya existe un episodio para ``source_session_id`` (idempotencia).

    Chequeo previo barato (espeja el UNIQUE(session_id) de episodic_memory): si el
    episodio ya existe, el worker no re-resume ni re-inserta (un doble cierre no
    duplica). El IntegrityError de la UNIQUE sigue siendo la red final ante una
    carrera entre dos workers entre este SELECT y el INSERT.
    """
    stmt = (
        select(func.count())
        .select_from(EpisodicMemory)
        .where(EpisodicMemory.session_id == source_session_id)
    )
    return ((await session.execute(stmt)).scalar_one() or 0) > 0


async def _consolidate_session_in_db(
    *,
    session: AsyncSession,
    user_id: UUID,
    source_session_id: UUID,
    mode: str,
    origin_mode: Mode | None,
    llm_client: LLMClient,
    embedder: EmbeddingClient,
    reranker: Reranker,
    retention_config: RetentionConfig,
) -> int:
    """Nucleo de la consolidacion episodica sobre una ``session`` ya abierta.

    Retorna 1 si se persistio un episodio nuevo, 0 si no (0 turnos, summary vacio,
    o episodio ya existente). NO commitea: el commit lo da el caller
    (``_async_consolidate_session`` en prod, o el fixture en tests).
    """
    # Idempotencia: si el episodio ya existe, no-op (doble cierre / reintento).
    if await _episode_exists(session, source_session_id):
        logger.info("consolidate_session: episodio ya existe session=%s, no-op", source_session_id)
        return 0

    turns_store = ConversationTurnStore(session, user_id)
    turns = await turns_store.list_for_session(source_session_id)
    if not turns:
        # Sin turnos no hay nada que resumir: NO se crea un episodio vacio.
        logger.info("consolidate_session: 0 turnos session=%s, no-op", source_session_id)
        return 0

    transcript = _build_transcript(turns)
    mem_engine = QwenMemoryEngine(llm_client)
    summary = await mem_engine.summarize(transcript=transcript, mode=mode)
    if not summary.summary:
        # Resumen vacio (LLM degradado / JSON corrupto): NO se persiste un episodio
        # sin contenido. Los turnos NO se purgan: un reintento futuro podria resumir.
        logger.info("consolidate_session: resumen vacio session=%s, no-op", source_session_id)
        return 0

    is_sensitive = origin_mode == Mode.BIENESTAR
    # retention_days config-driven (ADR-007 D2): sensible vs default salen del
    # RetentionConfig (``ynara.config.json[memory]``), no de constantes. El cap
    # duro (<=365 para sensibles) lo enforcea el model_validator de
    # EpisodicMemoryCreate + la CHECK constraint.
    retention_days = (
        retention_config.retention_sensitive_days
        if is_sensitive
        else retention_config.retention_default_days
    )
    payload = EpisodicMemoryCreate(
        session_id=source_session_id,
        summary=summary.summary,
        occurred_at=datetime.now(UTC),
        is_sensitive=is_sensitive,
        retention_days=retention_days,
        topics=summary.topics,
    )

    episodic_store = EpisodicMemoryStore(session, user_id, embedder, reranker)
    audit_store = AuditStore(session, user_id)

    try:
        out = await episodic_store.add(payload)
    except IntegrityError:
        # Carrera: otro worker inserto el episodio entre el SELECT y el INSERT. La
        # UNIQUE(session_id) lo rechaza -> degradar a no-op (no se duplica). Se
        # revierte el estado parcial de esta op para no envenenar la transaccion.
        await session.rollback()
        logger.info(
            "consolidate_session: IntegrityError (UNIQUE session_id) session=%s, no-op",
            source_session_id,
        )
        return 0

    # Auditoria: una fila WRITE/EPISODIC con record_hash del summary (regla #4: el
    # hash es unidireccional, NUNCA el summary en claro). sensitive espeja la fila.
    await audit_store.record(
        operation=AuditOperation.WRITE,
        target_layer=MemoryLayer.EPISODIC,
        target_id=out.id,
        record_hash=compute_record_hash(summary.summary),
        origin_model=LlmModel.QWEN,
        origin_mode=origin_mode,
        sensitive=is_sensitive,
    )

    # Purga de los turnos crudos: su resumen ya quedo en episodic_memory. summary +
    # purge van en el MISMO commit (atomicidad): el episodio existe sii los turnos
    # se borraron.
    purged = await turns_store.purge_session(source_session_id)
    logger.info(
        "consolidate_session: episodio creado session=%s turnos_purgados=%d",
        source_session_id,
        purged,
    )
    return 1


async def _async_consolidate_session(
    *,
    user_id: str,
    session_id: str,  # str(ChatSession.id): se parsea a UUID (FK episodic.session_id)
    mode: str,
    # Inyectables para tests (None => construir desde get_settings())
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    embedder: EmbeddingClient | None = None,
    reranker: Reranker | None = None,
    # retention config inyectable para tests (None => cargar de ynara.config.json)
    retention_config: RetentionConfig | None = None,
    # session inyectable para tests de integracion (evita crear engine nuevo)
    session: AsyncSession | None = None,
) -> int:
    """Nucleo async de la consolidacion episodica; retorna 1 si creo un episodio, 0 si no.

    Si ``session`` se inyecta (tests), se usa directamente y NO se crea engine ni
    se commitea (el fixture controla el ciclo de vida). Si es ``None`` (worker
    Celery en prod), se construye el engine con ``NullPool`` (decision #4 M8), se
    abre la sesion, se commitea y se dispone el engine.

    ``session_id`` es ``str(ChatSession.id)`` (FK a ``sessions.id``). Si el parse a
    UUID falla (payload corrupto en la cola), se degrada a no-op (0) SIN crashear:
    el episodio requiere una FK real, no se puede crear con un session_id basura.
    """
    cfg = settings or get_settings()

    effective_llm = llm_client or _build_consolidation_llm(cfg)
    effective_embedder = embedder or _build_embedder(cfg)
    effective_reranker = reranker or _build_reranker(cfg)
    # Retention config-driven (ADR-007 D2): inyectado en tests, o cargado de
    # ``ynara.config.json[memory]`` en prod. Fallback defensivo: si el config es
    # ilegible/invalido NO se tumba el worker (regla del modulo: un fallo de config
    # nunca mata la consolidacion) -> se usa el RetentionConfig por defaults (=los
    # valores historicos). El ``try/except`` del task sigue siendo la red final.
    effective_retention = retention_config or _load_retention_config_safe()

    uid = UUID(user_id)
    source_session_id = _parse_source_session_id(session_id)
    if source_session_id is None:
        # session_id no-UUID: el episodio requiere una FK real -> no-op sin crash.
        return 0
    origin_mode = _parse_origin_mode(mode)

    if session is not None:
        # Modo test: usar la sesion inyectada, no crear engine ni commitear.
        return await _consolidate_session_in_db(
            session=session,
            user_id=uid,
            source_session_id=source_session_id,
            mode=mode,
            origin_mode=origin_mode,
            llm_client=effective_llm,
            embedder=effective_embedder,
            reranker=effective_reranker,
            retention_config=effective_retention,
        )

    # Modo produccion: engine NullPool efimero; worker_session commitea al salir
    # del bloque y dispone el engine (decision #4 centralizada en _engine.py).
    async with worker_session(cfg) as db_session:
        return await _consolidate_session_in_db(
            session=db_session,
            user_id=uid,
            source_session_id=source_session_id,
            mode=mode,
            origin_mode=origin_mode,
            llm_client=effective_llm,
            embedder=effective_embedder,
            reranker=effective_reranker,
            retention_config=effective_retention,
        )


@celery_app.task(bind=True, name="workflows.consolidate_session")
def consolidate_session(
    self,  # bind=True, self no se usa (sin retry manual en M10)
    *,
    user_id: str,
    session_id: str,
    mode: str = Mode.VIDA.value,
) -> None:
    """Task Celery: al cerrar la sesion, resume sus turnos en ``episodic_memory``.

    Firma 100% strings/primitivos (``task_serializer='json'``). NUNCA cruza el
    wire un ``AsyncSession``, un ``LLMClient``, un ``UUID`` ni un store.

    El cuerpo async se corre con ``asyncio.run`` (worker prefork de Celery). Todo
    el bloque se envuelve en ``try/except``: un fallo NO tumba el worker (loguea un
    mensaje SIN el contenido del usuario, regla #4).

    Args:
        user_id: UUID del usuario como string (JSON-safe).
        session_id: ``str(ChatSession.id)`` (FK a ``sessions.id`` / a
            ``episodic_memory.session_id``). El enqueue post-commit (desde
            ``close_session``) garantiza que la ``ChatSession`` ya este persistida.
        mode: Modo de la sesion (p.ej. 'bienestar' -> ``is_sensitive=True``).
            Default ``vida`` para tolerar un payload viejo sin ``mode``.
    """
    try:
        created = asyncio.run(
            _async_consolidate_session(
                user_id=user_id,
                session_id=session_id,
                mode=mode,
            )
        )
        logger.info(
            "consolidate_session: user=%s session=%s created=%d",
            user_id,
            session_id,
            created,
        )
    except Exception as exc:
        # Regla: el worker NUNCA muere por un fallo de consolidacion episodica.
        # regla #4: logger.error (NO logger.exception): el traceback / str(exc) podria
        # arrastrar contenido de usuario a los logs. Se loguea solo el TIPO de excepcion.
        logger.error(
            "consolidate_session: fallo user=%s session=%s: %s (sin datos de usuario)",
            user_id,
            session_id,
            type(exc).__name__,
        )
