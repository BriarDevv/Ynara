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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
    MemoryPatchRequest,
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
    if layer is MemoryLayer.PROCEDURAL:
        # Procedural: la ref es la ``key`` (str), no un UUID.
        procedural = ProceduralMemoryStore(session, user_id)
        deleted = await procedural.delete(ref)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
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
    await session.commit()  # persistir el borrado (ver nota en update_memory).
    return Response(status_code=status.HTTP_204_NO_CONTENT)
