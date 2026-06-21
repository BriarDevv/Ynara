"""Endpoints HTTP de la memoria privada del usuario: ``/v1/memory``.

La superficie privacy-first donde el **dueño** ve, exporta, edita y borra su propia
memoria con su JWT: tres GET (list/detail/export) + PATCH/DELETE individual por capa
+ wipe total (dry-run + confirm). Las mutaciones (PATCH/DELETE/wipe) escriben en
``audit_log`` (issue #161).

Decisiones de diseño (cerradas con producto, NO re-litigar):

(1) El dueño ve su memoria COMPLETA. Se reusan los ``*Out`` sagrados
    (``SemanticMemoryOut`` / ``EpisodicMemoryOut`` / ``ProceduralMemoryOut``) que ya
    exponen el ``content`` / ``summary`` **descifrado** + la metadata. El blob
    cifrado crudo NUNCA viaja: los stores descifran fila por fila y construyen el
    ``Out`` con plaintext. El riesgo de regurgitación del MODELO (la tool
    ``memory.search`` proyecta solo ``{id, content, importance}``) NO aplica al
    dueño por HTTP con su token.

(2) La capa va en el PATH (``/memory/{layer}/{ref}``), no un ``/memory/{id}`` plano:
    evita el oráculo cross-tabla (probar un id contra las 3 tablas para inferir
    cuál existe). El ``layer`` es un ``MemoryLayer`` (FastAPI da 422 si no es una
    de las 3 capas).

(3) AISLAMIENTO sin oráculo (igual que ``sessions.py`` / ``chat.py``). Todo query
    filtra por el ``user_id`` del JWT (ligado en el ``__init__`` del store). Un
    ``GET /memory/{layer}/{ref}`` de OTRO usuario da el MISMO 404 (status + detail)
    que uno inexistente: ajena == inexistente, nunca se revela la existencia de
    memoria ajena. El store ya filtra por ``user_id``, así que una fila de otro
    user da ``None`` → 404.

(4) DECRYPT POST-OWNERSHIP. ``get_by_id`` (semantic/episodic) filtra por
    ``id`` + ``user_id`` y retorna ``None`` ANTES de tocar crypto si la fila no es
    del user: NUNCA se intenta descifrar el blob de otro usuario. La disciplina vive
    en el store; el endpoint solo mapea ``None`` → 404.

Mapeo de errores: 422 validación (``limit`` fuera de ``[1, 100]``, ``offset < 0``,
``layer`` inválida, ``ref`` no-UUID en semantic/episodic — todo Pydantic/FastAPI
automático), 401 sin token / token inválido (``get_current_user``), 404 ref
ajena/inexistente (mismo detail), 200 en el happy path.

Los stores se instancian por request ligando ``session`` + ``user_id`` (del JWT) +
embedder/reranker (de las deps, aunque ``list_all`` / ``get_by_id`` no embeddeen:
es lo menos invasivo, no se toca el ``__init__`` de los stores sagrados). El
procedural no lleva embedder.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.v1._http import too_many_requests
from app.api.v1._memory_stores import build_memory_stores
from app.core.config import get_settings
from app.core.deps import (
    CurrentUser,
    DbSession,
    TokenStoreDep,
    get_embedder,
    get_reranker,
)
from app.core.ratelimit import (
    check_memory_export_rate_limit,
    check_memory_search_rate_limit,
    check_memory_wipe_rate_limit,
)
from app.enums import AuditOperation, MemoryLayer
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.memory.audit import AuditStore
from app.memory.episodic import EpisodicMemoryStore
from app.memory.hashing import compute_record_hash, procedural_hash_payload
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.schemas.memory import (
    EpisodicMemoryOut,
    ProceduralMemoryOut,
    SemanticMemoryOut,
)
from app.schemas.memory_api import (
    EpisodicMemoryPage,
    MemoryExport,
    MemoryGroupedResponse,
    MemoryPatchRequest,
    MemorySearchHit,
    MemorySearchResponse,
    MemoryWipeConfirm,
    MemoryWipePreview,
    MemoryWipeResult,
    ProceduralMemoryPage,
    SemanticMemoryPage,
)

router = APIRouter()

# Default + cap de la paginación de ``GET /v1/memory`` (decisión de producto).
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 100

# Detail ÚNICO del 404 de ``/memory/{layer}/{ref}``: ajena e inexistente comparten
# exactamente este mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "memoria no encontrada"

# Detail del 405 de ``PATCH /memory/episodic/{ref}``: el summary lo genera el worker
# de consolidación; editar a mano "un resumen de lo que pasó" corrompe la
# trazabilidad. El dueño puede BORRAR un episodio (DELETE), no reescribirlo.
_EPISODIC_PATCH_NOT_ALLOWED = "el resumen episódico no se edita: se borra (DELETE) o se regenera"

# Versión del formato de export (``MemoryExport.version``). Bump al evolucionar.
_EXPORT_VERSION = 1

# Message del 409 de ``POST /v1/memory/wipe``: el confirm no matchea el recount actual.
# El cliente debe re-confirmar con un preview fresco (el detail trae los conteos actuales).
_WIPE_CONFLICT_MESSAGE = (
    "los conteos confirmados no coinciden con el estado actual; reintentá con un preview fresco"
)

# Detail del 422 de ``POST /v1/memory/wipe`` sin ``dry_run`` y sin body: el execute destructivo
# EXIGE el confirm per-layer (guarda de intención). El dry-run (``?dry_run=true``) no lo pide.
_WIPE_CONFIRM_REQUIRED = "el wipe destructivo requiere el confirm per-layer (o usá ?dry_run=true)"

EmbedderDep = Annotated[EmbeddingClient, Depends(get_embedder)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


async def _semantic_page(
    store: SemanticMemoryStore, *, limit: int, offset: int
) -> SemanticMemoryPage:
    """Arma la ``SemanticMemoryPage``: ``items`` paginados + ``total`` del user.

    ``count`` + ``list_all`` NO son atómicos (dos statements bajo READ COMMITTED): si el
    worker inserta/borra entre ambos, ``total`` puede diferir de la página por ~1 fila. Es
    el trade-off ACEPTADO de toda paginación (staleness benigno, se reconcilia en el próximo
    fetch). El export —que necesita consistencia total— usa ``list_all()`` sin ``count``.
    """
    items = await store.list_all(limit=limit, offset=offset)
    total = await store.count()
    # ``total or 0`` por consistencia con sessions.py (el COUNT siempre da int acá, pero
    # el patrón uniforme de las *Page del repo blinda un None hipotético).
    return SemanticMemoryPage(items=items, total=total or 0)


async def _episodic_page(
    store: EpisodicMemoryStore, *, limit: int, offset: int
) -> EpisodicMemoryPage:
    """Arma la ``EpisodicMemoryPage``: ``items`` paginados + ``total`` del user.

    ``count`` + ``list_all`` no atómicos (TOCTOU benigno de paginación): ver ``_semantic_page``.
    """
    items = await store.list_all(limit=limit, offset=offset)
    total = await store.count()
    # ``total or 0`` por consistencia con sessions.py (ver nota en ``_semantic_page``).
    return EpisodicMemoryPage(items=items, total=total or 0)


async def _procedural_page(
    store: ProceduralMemoryStore, *, limit: int, offset: int
) -> ProceduralMemoryPage:
    """Arma la ``ProceduralMemoryPage``: ``items`` paginados en DB + ``total`` del user.

    Paginación en Postgres (``limit``/``offset``) + ``count()``, igual que
    ``_semantic_page`` / ``_episodic_page``. Antes ``list_all()`` traía TODAS las
    filas y la página se recortaba en Python (no escalaba si la capa crecía). El
    ``count`` + ``list_all`` no son atómicos (TOCTOU benigno: ver ``_semantic_page``).
    """
    items = await store.list_all(limit=limit, offset=offset)
    total = await store.count()
    return ProceduralMemoryPage(items=items, total=total)


def _parse_uuid_ref(ref: str) -> UUID:
    """Parsea la ``ref`` polimórfica a UUID (semantic/episodic). 422 si no parsea.

    La ``ref`` es ``str`` en la firma porque para procedural es una ``key``; para
    semantic/episodic debe ser un UUID. Espeja el 422 que daría un path param
    tipado ``UUID`` (acá es manual porque la ref cambia de tipo según la capa).
    """
    try:
        return UUID(ref)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ref no es un UUID válido",
        ) from exc


@router.get("/memory", response_model=None, status_code=200)
async def list_memory(
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    layer: Annotated[MemoryLayer | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIMIT_MAX)] = _LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemoryGroupedResponse | SemanticMemoryPage | EpisodicMemoryPage | ProceduralMemoryPage:
    """Lista la memoria del usuario, opcionalmente filtrada por ``?layer=``.

    - Sin ``?layer=``: respuesta AGRUPADA (``MemoryGroupedResponse``) con las 3
      capas, cada una con sus ``items`` (página ``limit``/``offset``) y su ``total``.
    - Con ``?layer=<capa>``: solo la ``*Page`` de esa rama.

    ``limit`` ∈ ``[1, 100]`` (default 50), ``offset`` ≥ 0: FastAPI devuelve 422 si
    se salen del rango. Todo filtra por el ``user_id`` del JWT (aislamiento). NO se
    embeddea (es un listado, no una búsqueda); los stores reciben embedder/reranker
    solo porque su ``__init__`` sagrado los pide.

    Returns:
        ``MemoryGroupedResponse`` (sin ``layer``) o la ``*Page`` de la capa pedida.
    """
    semantic, episodic, procedural = build_memory_stores(
        session, user_id, embedder=embedder, reranker=reranker
    )

    if layer is MemoryLayer.SEMANTIC:
        return await _semantic_page(semantic, limit=limit, offset=offset)
    if layer is MemoryLayer.EPISODIC:
        return await _episodic_page(episodic, limit=limit, offset=offset)
    if layer is MemoryLayer.PROCEDURAL:
        return await _procedural_page(procedural, limit=limit, offset=offset)

    # Sin layer: las 3 capas agrupadas (misma página por capa).
    return MemoryGroupedResponse(
        semantic=await _semantic_page(semantic, limit=limit, offset=offset),
        episodic=await _episodic_page(episodic, limit=limit, offset=offset),
        procedural=await _procedural_page(procedural, limit=limit, offset=offset),
    )


@router.get("/memory/export", status_code=200)
async def export_memory(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> JSONResponse:
    """Exporta las 3 capas COMPLETAS del usuario como un JSON versionado descargable.

    Sin paginar (on-prem, pocos hechos por user; no hace falta streaming). Trae las
    3 capas enteras descifradas, agrega ``version`` + ``exported_at``
    (``datetime.now(UTC)``) y devuelve un ``JSONResponse`` con header
    ``Content-Disposition: attachment`` para que el cliente lo baje como archivo.
    Todo filtra por el ``user_id`` del JWT (solo la memoria del dueño).

    Esta ruta va ANTES de ``/memory/{layer}/{ref}`` en el router: ``export`` es una
    ruta estática y debe matchear antes que el path param ``{layer}`` (que es un
    ``MemoryLayer`` y no incluye ``export``, pero el orden explícito lo blinda).

    Rate-limit (S4, P1 seguridad): es el endpoint más caro (descifra 3 capas sin
    paginar). Bucket por ``user_id`` (del JWT), chequeado ANTES de instanciar stores
    o descifrar nada. fail-open si Redis cae (sin freno, baseline). 429 con
    ``Retry-After`` (mismo shape que ``auth.py``) si se cruza el techo de la ventana.

    Returns:
        ``JSONResponse`` con el ``MemoryExport`` serializado y el header de descarga.
    """
    if not await check_memory_export_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_export_window_seconds)
    semantic, episodic, procedural = build_memory_stores(
        session, user_id, embedder=embedder, reranker=reranker
    )

    # Capas completas, sin paginar y en UN query por capa (``list_all`` sin
    # ``limit`` trae todo): evita el ``count()``-para-el-limit y su TOCTOU (una
    # fila escrita por el worker entre el count y el select se perdería).
    export = MemoryExport(
        version=_EXPORT_VERSION,
        exported_at=datetime.now(UTC),
        semantic=await semantic.list_all(),
        episodic=await episodic.list_all(),
        procedural=await procedural.list_all(),
    )
    return JSONResponse(
        content=export.model_dump(mode="json"),
        headers={"Content-Disposition": 'attachment; filename="ynara-memory-export.json"'},
    )


@router.post("/memory/wipe", response_model=None, status_code=200)
async def wipe_memory(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    body: MemoryWipeConfirm | None = None,
    dry_run: Annotated[bool, Query()] = False,
) -> MemoryWipePreview | MemoryWipeResult:
    """Previsualiza (``?dry_run=true``) o ejecuta el wipe TOTAL de la memoria del usuario.

    **Un solo POST** para las dos operaciones, distinguidas por ``?dry_run``:

    - ``?dry_run=true`` → **PREVIEW** (read-only): cuenta las 3 capas del user
      (``count()`` por store; no muta, no commitea, no descifra) y devuelve
      ``MemoryWipePreview`` con los conteos por capa + ``total`` (la suma). El ``body``
      se ignora (no hace falta confirm para previsualizar). El cliente usa estos números
      como los ``expected_*`` del execute.
    - ``dry_run`` ausente o ``false`` → **EXECUTE** (destructivo, irreversible): exige el
      ``body`` (``MemoryWipeConfirm``); si falta → **422**. Reconcuenta + compara contra
      los ``expected_*`` y borra o aborta (ver flujo abajo). **Rate-limited** por ``user_id``
      (techo bajo por hora, antes de tocar la DB); el preview no consume cuota. **429** con
      ``Retry-After`` si se cruza el techo. fail-open si Redis cae.

    El preview vive en un POST (no en un GET) A PROPÓSITO: un GET debe ser seguro e
    idempotente, pero ``/memory/wipe`` es la superficie de una operación DESTRUCTIVA; un
    prefetch / crawler que dispare un GET no debe tocarla siquiera para previsualizar. El
    preview es read-only igual, pero se mueve al verbo no-seguro para que NUNCA lo gatille
    una navegación accidental. El shape del preview es idéntico al del viejo GET.

    Esta ruta estática va ANTES de ``/memory/{layer}/{ref}`` en el router (igual que
    ``export``): no hay POST sobre el path param, pero el orden explícito lo blinda y queda
    legible.

    --- PREVIEW (``?dry_run=true``) ---
    Siempre 200, incluso todo en 0: un user sin memoria es un estado VÁLIDO, jamás 404 (un
    preview ``{0,0,0,0}`` es una respuesta legítima). Solo viajan enteros (regla #4): ningún
    ``content`` / ``summary``.

    --- EXECUTE (sin ``dry_run``) ---
    Operación SAGRADA (toca ``app/memory/``, regla #3): hard-delete físico de TODO lo del
    user en las 3 capas, con una guarda de intención (el confirm per-layer) para evitar
    borrados accidentales / doble-click.

    Flujo (atomicidad: recount + wipe + commit en la MISMA transacción del request):

    1. **Reconcuenta** las 3 capas (``count()`` por store) — el estado ACTUAL.
    2. Si ``(semantic, episodic, procedural)`` actuales **no** coinciden con los ``expected_*``
       del body → **409 Conflict** con los conteos ACTUALES en el ``detail`` (para que el
       cliente re-confirme con un preview fresco). **NADA** se borra ni se commitea.
    3. Si coinciden → ``wipe()`` de las 3 capas (capturando el ``rowcount`` REAL de cada una),
       ``await session.commit()`` y devuelve **200** ``MemoryWipeResult`` con los conteos
       REALMENTE borrados.

    TOCTOU: el confirm es una guarda de INTENCIÓN (prueba que el humano vio el plan), NO cirugía
    exacta. El ``DELETE WHERE user_id`` barre el estado presente COMPLETO al momento del
    ``DELETE``, así que el receipt reporta el ``rowcount`` REAL (puede diferir del preview si el
    worker insertó entre el recount y el wipe — pero el confirm contra el recount ya habría dado
    409 en ese caso; si pasó el guard, el rowcount es la verdad de lo borrado). READ COMMITTED
    (default del repo) alcanza.

    IDEMPOTENCIA: wipe de user vacío con confirm ``{0,0,0}`` → 200 ``{0,0,0,0}``. Un segundo
    wipe seguido (preview ``{0,0,0}``, confirm ``{0,0,0}``) → 200 ``{0,0,0,0}``. Jamás 404. Un
    confirm viejo ``{N,..}`` tras ya haber wipeado → 409 (anti-doble-click).

    El ``commit`` va SOLO en el happy path: un 409/422/401 no muta ni commitea (``get_db`` no
    commitea —cierra → rollback—). Todo filtra por el ``user_id`` del JWT (aislamiento). Ni el
    recount ni el wipe descifran ni logean contenido (regla #4: solo enteros viajan).

    Returns:
        ``MemoryWipePreview`` (con ``?dry_run=true``) o ``MemoryWipeResult`` (execute) con
        los conteos por capa + ``total``.
    """
    # EXECUTE rate-limit (P1 seguridad): el wipe destructivo es por-usuario y caro de
    # auditar; el preview (dry_run) es read-only y NO se frena. Chequeado ANTES de tocar la
    # DB. fail-open si Redis cae. 429 con Retry-After (mismo shape que export/auth).
    if not dry_run and not await check_memory_wipe_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_wipe_window_seconds)
    semantic, episodic, procedural = build_memory_stores(
        session, user_id, embedder=embedder, reranker=reranker
    )

    # 1. Recontar el estado ACTUAL de las 3 capas (en la misma transacción del wipe, así el
    #    preview y el execute ven exactamente el mismo COUNT).
    sem_count = await semantic.count()
    epi_count = await episodic.count()
    proc_count = await procedural.count()

    # --- PREVIEW: read-only, no muta ni commitea, ignora el body. ---
    if dry_run:
        return MemoryWipePreview(
            semantic=sem_count,
            episodic=epi_count,
            procedural=proc_count,
            total=sem_count + epi_count + proc_count,
        )

    # --- EXECUTE: el confirm per-layer es obligatorio (guarda de intención). ---
    if body is None:
        # Sin dry_run y sin body: el execute destructivo no tiene la guarda de intención. 422
        # (no muta nada): el cliente debe mandar el confirm o pedir ?dry_run=true.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_WIPE_CONFIRM_REQUIRED,
        )

    # 2. Guarda de intención: el confirm per-layer debe matchear el recount o se aborta.
    if (
        body.expected_semantic != sem_count
        or body.expected_episodic != epi_count
        or body.expected_procedural != proc_count
    ):
        # 409 con los conteos ACTUALES (solo enteros, regla #4): el cliente re-confirma con un
        # preview fresco. NADA se borró ni se commiteó.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": _WIPE_CONFLICT_MESSAGE,
                "semantic": sem_count,
                "episodic": epi_count,
                "procedural": proc_count,
                "total": sem_count + epi_count + proc_count,
            },
        )

    # 3. Match: hard-delete de las 3 capas, capturando el rowcount REAL de cada una.
    sem_wiped = await semantic.wipe()
    epi_wiped = await episodic.wipe()
    proc_wiped = await procedural.wipe()

    # AUDIT (issue #161): una fila por CADA capa con borrado EFECTIVO (rowcount > 0). El wipe
    # es DELETE-by-user masivo: no hay target_id ni record per-entry, así que target_id=None y el
    # record_hash ata la fila a "el wipe de esta capa" (sha256 de ``wipe:<capa>``). Las capas con
    # 0 borrados NO generan fila (no hubo destrucción que auditar). EPISODIC va sensitive=True de
    # forma CONSERVADORA: el wipe pudo arrasar episodios sensibles y no podemos chequear per-entry
    # (es un DELETE masivo, no leemos is_sensitive fila por fila); semantic/procedural nunca son
    # sensibles. origin_* quedan None (acción del usuario por HTTP, sin LLM/tool: distingue el
    # audit de endpoint del de consolidación, que lleva origin_model=QWEN). La fila va en la MISMA
    # transacción que el wipe, antes del único commit -> wipe + audit son ATÓMICOS (todo o nada).
    audit = AuditStore(session, user_id)
    if sem_wiped > 0:
        await audit.record(
            operation=AuditOperation.DELETE,
            target_layer=MemoryLayer.SEMANTIC,
            target_id=None,
            record_hash=compute_record_hash(f"wipe:{MemoryLayer.SEMANTIC.value}"),
            sensitive=False,
        )
    if epi_wiped > 0:
        await audit.record(
            operation=AuditOperation.DELETE,
            target_layer=MemoryLayer.EPISODIC,
            target_id=None,
            record_hash=compute_record_hash(f"wipe:{MemoryLayer.EPISODIC.value}"),
            sensitive=True,
        )
    if proc_wiped > 0:
        await audit.record(
            operation=AuditOperation.DELETE,
            target_layer=MemoryLayer.PROCEDURAL,
            target_id=None,
            record_hash=compute_record_hash(f"wipe:{MemoryLayer.PROCEDURAL.value}"),
            sensitive=False,
        )

    # Persistir el wipe (los stores solo hacen flush; get_db no commitea -> sin esto el borrado
    # no persistiría en prod). Va solo en el happy path: un 409/422 no muta y no debe commitear.
    await session.commit()
    return MemoryWipeResult(
        semantic=sem_wiped,
        episodic=epi_wiped,
        procedural=proc_wiped,
        total=sem_wiped + epi_wiped + proc_wiped,
    )


# --- Búsqueda semántica (GET /v1/memory/search) ---------------------------------
# Top-N por capa SEMÁNTICAMENTE buscable (semantic + episodic). El `score` es un
# proxy por RANK con el mismo decaimiento que el mock del front (contrato de
# presentación): el reranker del store no expone su score crudo y la firma sagrada
# (`app/memory/`) no se toca (regla #3). Procedural NO entra: es key-value, el store
# no embeddea ni hace búsqueda semántica.
_SEARCH_LIMIT_PER_LAYER = 10
_SEARCH_SCORE_TOP = 0.95
_SEARCH_SCORE_STEP = 0.08
_SEARCH_SCORE_FLOOR = 0.5


def _rank_score(index: int) -> float:
    """Score 0..1 decreciente por posición (proxy de relevancia; ver ``MemorySearchHit``)."""
    return max(_SEARCH_SCORE_FLOOR, _SEARCH_SCORE_TOP - index * _SEARCH_SCORE_STEP)


def _build_search_response(
    query: str,
    semantic_results: list[SemanticMemoryOut],
    episodic_results: list[EpisodicMemoryOut],
) -> MemorySearchResponse:
    """Mapea los ``*Out`` ya rankeados (semantic + episodic) al envelope de búsqueda.

    Orden: primero los hechos (semantic), luego los momentos (episodic) — espeja el
    mock del front. El ``score`` se asigna por posición en la lista combinada
    (``_rank_score(len(results))`` en cada append). ``ref`` = UUID; ``snippet`` =
    ``content`` / ``summary`` ya descifrado por el store; ``occurred_at`` =
    ``created_at`` (semantic) / ``occurred_at`` (episodic).
    """
    results: list[MemorySearchHit] = []
    for sem in semantic_results:
        results.append(
            MemorySearchHit(
                layer=MemoryLayer.SEMANTIC,
                ref=str(sem.id),
                snippet=sem.content,
                score=_rank_score(len(results)),
                occurred_at=sem.created_at,
            )
        )
    for epi in episodic_results:
        results.append(
            MemorySearchHit(
                layer=MemoryLayer.EPISODIC,
                ref=str(epi.id),
                snippet=epi.summary,
                score=_rank_score(len(results)),
                occurred_at=epi.occurred_at,
            )
        )
    return MemorySearchResponse(query=query, total=len(results), results=results)


@router.get("/memory/search", response_model=MemorySearchResponse, status_code=200)
async def search_memory(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> MemorySearchResponse:
    """Búsqueda semántica en la memoria del usuario (hechos + momentos).

    - ``q`` es la query (requerida; 1..200 chars → 422 fuera de rango). El front la
      dispara con ≥2 chars; acá una query en blanco tras ``strip`` devuelve un
      resultado vacío (200, no 422).
    - Corre el pipeline del store (embed → ANN top-K → descifrar → rerank) sobre las
      capas semánticamente buscables (``SemanticMemoryStore`` / ``EpisodicMemoryStore``),
      top-``_SEARCH_LIMIT_PER_LAYER`` por capa. NO toca ``app/memory/`` (regla #3):
      solo llama a ``search`` (read).
    - AISLAMIENTO: los stores filtran por ``user_id`` (del JWT) en el ``__init__``;
      jamás se busca en memoria ajena.

    Rate-limit (S4, P1 seguridad): el search dispara el pipeline caro embed → ANN →
    rerank (GPU/CPU) en cada query. Bucket por ``user_id``, chequeado ANTES de instanciar
    stores o correr el pipeline. Va DESPUÉS del short-circuit de query en blanco (una
    query vacía no corre pipeline, así que no consume cuota). fail-open si Redis cae.
    429 con ``Retry-After`` (mismo shape que export/wipe) si se cruza el techo.

    Regla #4: el ``snippet`` viaja descifrado (el store descifra in-process); el blob
    cifrado nunca entra a la respuesta. ``score`` es un proxy por rank.
    """
    query = q.strip()
    if not query:
        return MemorySearchResponse(query=q, total=0, results=[])

    if not await check_memory_search_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_search_window_seconds)

    semantic, episodic, _procedural = build_memory_stores(
        session, user_id, embedder=embedder, reranker=reranker
    )
    semantic_results = await semantic.search(query, limit=_SEARCH_LIMIT_PER_LAYER)
    episodic_results = await episodic.search(query, limit=_SEARCH_LIMIT_PER_LAYER)
    return _build_search_response(query, semantic_results, episodic_results)


@router.get("/memory/{layer}/{ref}", response_model=None, status_code=200)
async def get_memory(
    layer: MemoryLayer,
    ref: str,
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> SemanticMemoryOut | EpisodicMemoryOut | ProceduralMemoryOut:
    """Devuelve UN ítem de memoria del usuario por capa + referencia.

    - ``layer`` ∈ ``{semantic, episodic, procedural}`` (422 si no).
    - ``ref``: UUID para semantic/episodic (422 si no parsea), ``key`` (str) para
      procedural.
    - Si la ref no existe O pertenece a otro usuario → **404** con el MISMO
      ``detail`` (``_NOT_FOUND_DETAIL``): sin oráculo de existencia ajena. El store
      filtra por ``user_id``, así que una fila de otro user devuelve ``None`` → 404,
      sin haber intentado descifrarla (decrypt post-ownership).

    Returns:
        El ``*Out`` sagrado de la capa (``SemanticMemoryOut`` / ``EpisodicMemoryOut``
        / ``ProceduralMemoryOut``) con el contenido descifrado + metadata.
    """
    if layer is MemoryLayer.PROCEDURAL:
        # Procedural: la ref es la ``key`` (str), no un UUID.
        procedural = ProceduralMemoryStore(session, user_id)
        proc_item = await procedural.get(ref)
        if proc_item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        return proc_item

    # Semantic / Episodic: la ref es un UUID. 422 si no parsea (igual que un path
    # param tipado UUID; acá es manual porque la ref es polimórfica por capa).
    memory_id = _parse_uuid_ref(ref)

    if layer is MemoryLayer.SEMANTIC:
        semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
        sem_item = await semantic.get_by_id(memory_id)
        if sem_item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        return sem_item

    # layer is EPISODIC (las 3 ramas de MemoryLayer están cubiertas).
    episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
    epi_item = await episodic.get_by_id(memory_id)
    if epi_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    return epi_item


@router.patch("/memory/{layer}/{ref}", response_model=None, status_code=200)
async def update_memory(
    layer: MemoryLayer,
    ref: str,
    body: MemoryPatchRequest,
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> SemanticMemoryOut | ProceduralMemoryOut:
    """Edita UN ítem de memoria del usuario por capa + referencia.

    El dueño edita su propia memoria con su JWT. La mutación es **polimórfica por
    capa** y respeta el aislamiento estructural (los stores filtran por ``user_id``):

    - ``semantic``: actualiza el ``content``. Body requiere ``content`` (str no
      vacío). ``semantic.update(UUID(ref), content)`` re-embeddea + re-cifra y filtra
      por ``id`` **y** ``user_id``; ``None`` (inexistente o ajeno) → **404** con
      ``_NOT_FOUND_DETAIL`` (sin oráculo, sin descifrar nada ajeno). Devuelve
      ``SemanticMemoryOut`` con el ``content`` plaintext actualizado.
    - ``procedural``: actualiza el ``value`` (JSONB) de una key EXISTENTE. Body
      requiere ``value`` (dict). ``procedural.update(key, value)`` es un UPDATE puro
      (NO upsert): ``None`` si la key no existe o es ajena → **404** (jamás crea la
      key vía ``PATCH``). Devuelve ``ProceduralMemoryOut``.
    - ``episodic``: **405 Method Not Allowed**. El ``summary`` lo genera el worker de
      consolidación; reescribir a mano "un resumen de lo que pasó" corrompe la
      trazabilidad. El dueño puede BORRAR un episodio (``DELETE``), no reescribirlo.

    El body por capa se valida acá (el ``layer`` del path lo conoce el endpoint, no
    el schema): si el campo requerido para la capa falta → **422**. El ``content``
    vacío ya lo rechaza Pydantic (``min_length=1``) con 422.

    Returns:
        ``SemanticMemoryOut`` o ``ProceduralMemoryOut`` con el ítem actualizado.
    """
    if layer is MemoryLayer.EPISODIC:
        # 405: la capa no admite edición (no es 404 ni 200 — el método no se permite).
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail=_EPISODIC_PATCH_NOT_ALLOWED,
        )

    if layer is MemoryLayer.SEMANTIC:
        if body.content is None:
            # El body no corresponde a la capa: semantic exige ``content``.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="el PATCH semantic requiere 'content'",
            )
        memory_id = _parse_uuid_ref(ref)
        semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
        sem_item = await semantic.update(memory_id, body.content)
        if sem_item is None:
            # Inexistente o ajeno: mismo 404 que un GET (sin oráculo, no mutó nada).
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        # AUDIT (issue #161): tras el UPDATE EFECTIVO, antes del commit. record_hash = sha256 del
        # nuevo content (regla #4: digest, no plaintext); sensitive=False (semantic nunca lleva
        # contenido sensible). origin_* None: acción del usuario por HTTP. Misma transacción que
        # el update -> atómicos por el único commit del request (igual que memory_engine:484).
        await AuditStore(session, user_id).record(
            operation=AuditOperation.UPDATE,
            target_layer=MemoryLayer.SEMANTIC,
            target_id=sem_item.id,
            record_hash=compute_record_hash(body.content),
            sensitive=False,
        )
        # El store solo hace flush(): el commit del request lo da el endpoint (igual que
        # sessions.py:163 / chat.py:185 / auth.py:91). get_db NO commitea —cierra ->
        # rollback—, así que sin este commit la edición no persistiría en prod. Va solo
        # en el happy path: un 404/422 no muta nada y no debe commitear.
        await session.commit()
        return sem_item

    # layer is PROCEDURAL: la ref es la ``key`` (str). Exige ``value`` (dict).
    if body.value is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="el PATCH procedural requiere 'value'",
        )
    procedural = ProceduralMemoryStore(session, user_id)
    proc_item = await procedural.update(ref, body.value)
    if proc_item is None:
        # Key inexistente o ajena: 404 (NUNCA se crea vía PATCH — eso sería upsert).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    # AUDIT (issue #161): tras el UPDATE EFECTIVO, antes del commit. record_hash = sha256 del
    # payload canónico (key, value) — misma sede que la consolidación (memory_engine:518), así el
    # digest del mismo par da siempre lo mismo. sensitive=False; origin_* None (acción HTTP).
    await AuditStore(session, user_id).record(
        operation=AuditOperation.UPDATE,
        target_layer=MemoryLayer.PROCEDURAL,
        target_id=proc_item.id,
        record_hash=compute_record_hash(procedural_hash_payload(ref, body.value)),
        sensitive=False,
    )
    await session.commit()  # persistir la edición (ver nota en la rama semantic).
    return proc_item


@router.delete("/memory/{layer}/{ref}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    layer: MemoryLayer,
    ref: str,
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> Response:
    """Borra UN ítem de memoria del usuario por capa + referencia → **204** sin body.

    El dueño borra su propia memoria con su JWT, en las 3 capas. El aislamiento es
    estructural: los stores filtran el DELETE por ``id``/``key`` **y** ``user_id``,
    así que un ref ajeno o inexistente devuelve ``False`` → **404** con
    ``_NOT_FOUND_DETAIL`` (sin oráculo de existencia ajena, sin tocar data de otro
    usuario). El blob cifrado nunca viaja: el éxito es un 204 vacío.

    - ``semantic``: ``semantic.delete(UUID(ref))`` (``bool``). ``False`` → 404.
    - ``episodic``: ``episodic.delete(UUID(ref))`` (``bool``). ``False`` → 404.
    - ``procedural``: ``procedural.delete(key)`` (``bool``). ``False`` → 404.

    Returns:
        ``Response`` 204 No Content (sin cuerpo) en éxito.
    """
    audit = AuditStore(session, user_id)

    if layer is MemoryLayer.PROCEDURAL:
        # Procedural: la ref es la ``key`` (str), no un UUID.
        procedural = ProceduralMemoryStore(session, user_id)
        deleted = await procedural.delete(ref)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        # AUDIT (issue #161): tras el DELETE EFECTIVO, antes del commit. target_id=None (el
        # delete-by-key no retorna id; mismo criterio que memory_engine:527-534) y record_hash =
        # sha256 de la key ata la fila a la entrada borrada. sensitive=False; origin_* None.
        await audit.record(
            operation=AuditOperation.DELETE,
            target_layer=MemoryLayer.PROCEDURAL,
            target_id=None,
            record_hash=compute_record_hash(ref),
            sensitive=False,
        )
        await session.commit()  # persistir el borrado (ver nota en update_memory).
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Semantic / Episodic: la ref es un UUID (422 si no parsea).
    memory_id = _parse_uuid_ref(ref)

    if layer is MemoryLayer.SEMANTIC:
        semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
        deleted = await semantic.delete(memory_id)
    else:
        # layer is EPISODIC (las 3 ramas de MemoryLayer están cubiertas).
        episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
        deleted = await episodic.delete(memory_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    # AUDIT (issue #161): tras el DELETE EFECTIVO, antes del commit. record_hash = sha256 del id
    # (el contenido ya no existe; el id identifica la fila borrada, mismo criterio que
    # memory_engine:497-502). sensitive=True SOLO para episodic: es la única capa con contenido
    # sensible y se marca conservador SIN descifrar la entrada — sobre-marcar es fail-safe para
    # auditoría y consistente con el wipe episódico (evita descifrar la capa sensible solo para
    # leer un bool). origin_* None (acción del usuario por HTTP).
    await audit.record(
        operation=AuditOperation.DELETE,
        target_layer=layer,
        target_id=memory_id,
        record_hash=compute_record_hash(str(memory_id)),
        sensitive=(layer is MemoryLayer.EPISODIC),
    )
    await session.commit()  # persistir el borrado (ver nota en update_memory).
    return Response(status_code=status.HTTP_204_NO_CONTENT)
