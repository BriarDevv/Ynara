"""Endpoints HTTP de la memoria privada del usuario: ``/v1/memory`` (Ola 1, READ-ONLY).

La superficie privacy-first donde el **dueño** ve y exporta su propia memoria con
su JWT. Tres GET en esta ola; PATCH/DELETE/wipe son Olas 2-3.

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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.deps import (
    CurrentUser,
    DbSession,
    get_embedder,
    get_reranker,
)
from app.enums import MemoryLayer
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.memory.episodic import EpisodicMemoryStore
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

# Versión del formato de export (``MemoryExport.version``). Bump al evolucionar.
_EXPORT_VERSION = 1

EmbedderDep = Annotated[EmbeddingClient, Depends(get_embedder)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


async def _semantic_page(
    store: SemanticMemoryStore, *, limit: int, offset: int
) -> SemanticMemoryPage:
    """Arma la ``SemanticMemoryPage``: ``items`` paginados + ``total`` del user."""
    items = await store.list_all(limit=limit, offset=offset)
    total = await store.count()
    return SemanticMemoryPage(items=items, total=total)


async def _episodic_page(
    store: EpisodicMemoryStore, *, limit: int, offset: int
) -> EpisodicMemoryPage:
    """Arma la ``EpisodicMemoryPage``: ``items`` paginados + ``total`` del user."""
    items = await store.list_all(limit=limit, offset=offset)
    total = await store.count()
    return EpisodicMemoryPage(items=items, total=total)


async def _procedural_page(
    store: ProceduralMemoryStore, *, limit: int, offset: int
) -> ProceduralMemoryPage:
    """Arma la ``ProceduralMemoryPage``: ``items`` paginados + ``total`` del user.

    El store procedural no tiene paginación nativa (``list_all()`` sin args), así
    que la página se recorta en Python sobre la lista ordenada por ``key``. Para
    on-prem (pocas preferencias por user) es inocuo; ``total`` es el largo completo.
    """
    all_items = await store.list_all()
    page = all_items[offset : offset + limit]
    return ProceduralMemoryPage(items=page, total=len(all_items))


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
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)

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

    Returns:
        ``JSONResponse`` con el ``MemoryExport`` serializado y el header de descarga.
    """
    semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
    episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
    procedural = ProceduralMemoryStore(session, user_id)

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
    try:
        memory_id = UUID(ref)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ref no es un UUID válido",
        ) from exc

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
