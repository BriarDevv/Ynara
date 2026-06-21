"""Endpoints HTTP de la memoria privada del usuario: ``/v1/memory``.

La superficie privacy-first donde el **dueño** ve, exporta, busca, edita y borra su
propia memoria con su JWT: tres GET (list/detail/export) + search + PATCH/DELETE
individual por capa + wipe total (dry-run + confirm).

Esta capa es FINA: delega toda la orquestación de dominio en ``MemoryService``
(``app/services/memory.py``) y se queda solo con lo que es HTTP puro:

- **Inyección de deps** (session, user_id del JWT, embedder/reranker, token store).
- **Rate-limit** (Redis + settings) de las rutas caras (export, wipe-execute, search):
  bucket por ``user_id``, ANTES de tocar la DB; fail-open si Redis cae; 429 con
  ``Retry-After``. El preview del wipe y los listados baratos no se frenan.
- **Traducción de errores**: las excepciones de dominio del service
  (``MemoryServiceError`` y subclases) se mapean a ``HTTPException`` (status + detail)
  en ``_to_http``. Las validaciones de wire puro (``limit``/``offset`` fuera de rango,
  ``layer`` inválida) las hace FastAPI por firma (422).
- **commit** del happy path mutante (update/delete/wipe-execute): los stores hacen
  ``flush`` y el service agrega la fila de audit en la misma sesión; el ``commit``
  acá las persiste atómicamente (igual que ``sessions.py`` / ``chat.py`` / ``auth.py``;
  ``get_db`` no commitea). Un 4xx no muta ni commitea.
- **Shaping** de la respuesta: ``JSONResponse`` con header de descarga (export),
  ``Response`` 204 sin body (delete).

Mapeo de errores (status ↔ excepción de dominio): 422 ``InvalidMemoryRefError`` /
``MemoryFieldRequiredError`` / ``WipeConfirmRequiredError`` · 404
``MemoryItemNotFoundError`` (mismo detail para ajena e inexistente, sin oráculo) ·
405 ``EpisodicNotEditableError`` · 409 ``WipeCountMismatchError`` (con los conteos
actuales) · 429 rate-limit · 401 sin token (``get_current_user``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.v1._http import too_many_requests
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
from app.enums import MemoryLayer
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.schemas.memory import (
    EpisodicMemoryOut,
    ProceduralMemoryOut,
    SemanticMemoryOut,
)
from app.schemas.memory_api import (
    EpisodicMemoryPage,
    MemoryGroupedResponse,
    MemoryPatchRequest,
    MemorySearchResponse,
    MemoryWipeConfirm,
    MemoryWipePreview,
    MemoryWipeResult,
    ProceduralMemoryPage,
    SemanticMemoryPage,
)
from app.services.memory import (
    EpisodicNotEditableError,
    InvalidMemoryRefError,
    MemoryFieldRequiredError,
    MemoryItemNotFoundError,
    MemoryService,
    MemoryServiceError,
    WipeConfirmRequiredError,
    WipeCountMismatchError,
)

router = APIRouter()

# Default + cap de la paginación de ``GET /v1/memory`` (decisión de producto). Viven
# acá porque son los límites del ``Query()`` (validación de wire de FastAPI).
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 100

# Detail ÚNICO del 404 de ``/memory/{layer}/{ref}``: ajena e inexistente comparten
# exactamente este mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "memoria no encontrada"

# Detail del 422 cuando la ``ref`` de semantic/episodic no parsea a UUID.
_INVALID_REF_DETAIL = "ref no es un UUID válido"

# Detail del 405 de ``PATCH /memory/episodic/{ref}``: el summary lo genera el worker
# de consolidación; editar a mano "un resumen de lo que pasó" corrompe la
# trazabilidad. El dueño puede BORRAR un episodio (DELETE), no reescribirlo.
_EPISODIC_PATCH_NOT_ALLOWED = "el resumen episódico no se edita: se borra (DELETE) o se regenera"

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


def _service(
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbeddingClient,
    reranker: Reranker,
) -> MemoryService:
    """Construye el ``MemoryService`` por-request ligado al ``user_id`` del JWT."""
    return MemoryService(session, user_id, embedder=embedder, reranker=reranker)


def _to_http(exc: MemoryServiceError) -> HTTPException:
    """Traduce una señal de dominio del ``MemoryService`` a la ``HTTPException`` del contrato."""
    if isinstance(exc, InvalidMemoryRefError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_INVALID_REF_DETAIL
        )
    if isinstance(exc, MemoryFieldRequiredError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail)
    if isinstance(exc, WipeConfirmRequiredError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_WIPE_CONFIRM_REQUIRED
        )
    if isinstance(exc, MemoryItemNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
    if isinstance(exc, EpisodicNotEditableError):
        return HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail=_EPISODIC_PATCH_NOT_ALLOWED
        )
    if isinstance(exc, WipeCountMismatchError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": _WIPE_CONFLICT_MESSAGE,
                "semantic": exc.semantic,
                "episodic": exc.episodic,
                "procedural": exc.procedural,
                "total": exc.total,
            },
        )
    # Exhaustivo: todas las subclases de MemoryServiceError están mapeadas arriba. Un
    # tipo nuevo sin mapear es un bug → re-raise (500 explícito) antes que un detail vacío.
    raise exc  # pragma: no cover


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

    ``limit`` ∈ ``[1, 100]`` (default 50), ``offset`` ≥ 0: FastAPI devuelve 422 si se
    salen del rango. Todo filtra por el ``user_id`` del JWT (aislamiento).
    """
    service = _service(session, user_id, embedder, reranker)
    return await service.list_grouped(layer=layer, limit=limit, offset=offset)


@router.get("/memory/export", status_code=200)
async def export_memory(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> JSONResponse:
    """Exporta las 3 capas COMPLETAS del usuario como un JSON versionado descargable.

    Rate-limit (es el endpoint más caro: descifra 3 capas sin paginar): bucket por
    ``user_id``, chequeado ANTES de instanciar stores o descifrar nada; fail-open si
    Redis cae; 429 con ``Retry-After``. Esta ruta estática va ANTES de
    ``/memory/{layer}/{ref}`` en el router.

    Returns:
        ``JSONResponse`` con el ``MemoryExport`` serializado + header de descarga.
    """
    if not await check_memory_export_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_export_window_seconds)
    service = _service(session, user_id, embedder, reranker)
    export = await service.export_all()
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

    - ``?dry_run=true`` → **PREVIEW** (read-only): cuenta las 3 capas y devuelve
      ``MemoryWipePreview``. El ``body`` se ignora; no consume cuota ni commitea.
    - ``dry_run`` ausente o ``false`` → **EXECUTE** (destructivo, irreversible):
      rate-limited por ``user_id`` (429 si se cruza el techo); exige el ``body``
      (``MemoryWipeConfirm``) o **422**; reconcuenta y si no matchea → **409** con los
      conteos actuales; si matchea, borra las 3 capas + audita y **commitea** (200 con
      los conteos REALMENTE borrados).

    El preview vive en un POST a propósito: un prefetch/crawler (GET) no debe tocar
    siquiera la superficie de una operación destructiva. Esta ruta estática va ANTES de
    ``/memory/{layer}/{ref}``.

    Returns:
        ``MemoryWipePreview`` (dry-run) o ``MemoryWipeResult`` (execute).
    """
    service = _service(session, user_id, embedder, reranker)
    if dry_run:
        return await service.wipe_preview()

    # EXECUTE: rate-limit ANTES de recontar/borrar (el preview no se frena). fail-open
    # si Redis cae. 429 con Retry-After (mismo shape que export/auth).
    if not await check_memory_wipe_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_wipe_window_seconds)
    try:
        result = await service.wipe_execute(body=body)
    except MemoryServiceError as exc:
        # 422 (sin confirm) o 409 (mismatch): NADA se borró ni se commitea.
        raise _to_http(exc) from exc
    # Persistir el wipe + las filas de audit atómicamente (get_db no commitea).
    await session.commit()
    return result


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

    - ``q`` es la query (requerida; 1..200 chars → 422 fuera de rango). Una query en
      blanco tras ``strip`` devuelve un resultado vacío (200, no 422) SIN consumir cuota.
    - Rate-limit (el search dispara el pipeline caro embed → ANN → rerank): bucket por
      ``user_id``, DESPUÉS del short-circuit de query en blanco y ANTES de instanciar
      stores o correr el pipeline; fail-open si Redis cae; 429 con ``Retry-After``.

    Regla #4: el ``snippet`` viaja descifrado (el store descifra in-process); el blob
    cifrado nunca entra a la respuesta. ``score`` es un proxy por rank.
    """
    query = q.strip()
    if not query:
        return MemorySearchResponse(query=q, total=0, results=[])

    if not await check_memory_search_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().memory_search_window_seconds)

    service = _service(session, user_id, embedder, reranker)
    return await service.search(query)


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
    - ``ref``: UUID para semantic/episodic (422 si no parsea), ``key`` para procedural.
    - Ref inexistente o ajena → **404** con el MISMO detail (sin oráculo de existencia
      ajena; el store filtra por ``user_id`` y no descifra nada ajeno).

    Returns:
        El ``*Out`` sagrado de la capa con el contenido descifrado + metadata.
    """
    service = _service(session, user_id, embedder, reranker)
    try:
        return await service.get_item(layer=layer, ref=ref)
    except MemoryServiceError as exc:
        raise _to_http(exc) from exc


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

    - ``semantic``: actualiza el ``content`` (body exige ``content`` no vacío). 404 si
      la ref es inexistente/ajena. Devuelve ``SemanticMemoryOut`` con el plaintext.
    - ``procedural``: actualiza el ``value`` (JSONB) de una key EXISTENTE (UPDATE puro,
      NO upsert; body exige ``value``). 404 si la key no existe o es ajena.
    - ``episodic``: **405** (el summary lo genera el worker; se borra, no se reescribe).

    El campo requerido por capa y el parseo de ``ref`` los valida el service y se mapean
    a 422; un 404/422/405 no muta nada. El happy path audita (issue #161) y commitea.

    Returns:
        ``SemanticMemoryOut`` o ``ProceduralMemoryOut`` con el ítem actualizado.
    """
    service = _service(session, user_id, embedder, reranker)
    try:
        item = await service.update_item(layer=layer, ref=ref, body=body)
    except MemoryServiceError as exc:
        raise _to_http(exc) from exc
    # Persistir la edición + la fila de audit atómicamente (el store solo hace flush;
    # get_db no commitea). Va solo en el happy path.
    await session.commit()
    return item


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

    El aislamiento es estructural (el store filtra el DELETE por ``id``/``key`` **y**
    ``user_id``): un ref ajeno o inexistente → **404** con el detail uniforme (sin
    oráculo, sin tocar data ajena). El happy path audita (issue #161) y commitea.

    Returns:
        ``Response`` 204 No Content (sin cuerpo) en éxito.
    """
    service = _service(session, user_id, embedder, reranker)
    try:
        await service.delete_item(layer=layer, ref=ref)
    except MemoryServiceError as exc:
        raise _to_http(exc) from exc
    # Persistir el borrado + la fila de audit atómicamente (ver nota en update_memory).
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
