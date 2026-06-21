"""Service de la memoria privada del usuario: capa de dominio de ``/v1/memory``.

Capa entre los endpoints (``app/api/v1/memory.py``) y los stores sagrados
(``app/memory/``). Encapsula TODA la orquestación de dominio: construir el triplete
de stores ligado al ``user_id`` del JWT, listar/exportar/buscar, leer/editar/borrar
un ítem por capa, el wipe total (preview + execute) y las escrituras en
``audit_log`` (issue #161). NO importa FastAPI (como ``services/auth.py``): señaliza
los caminos de error con **excepciones de dominio** que el endpoint traduce a HTTP.

Reparto de responsabilidades (router ↔ service):

- **Router (HTTP):** inyección de deps, rate-limit (Redis + settings), traducción
  ``excepción de dominio -> HTTPException`` (status + detail), ``commit`` del happy
  path mutante y el shaping de la respuesta (``JSONResponse`` con header de descarga
  del export, ``Response`` 204 del delete). Las validaciones de wire puro (rangos de
  ``limit``/``offset`` y la capa inválida) las hace FastAPI por firma.
- **Service (dominio):** lo demás. Las mutaciones hacen ``flush`` vía los stores +
  la fila de audit en la MISMA sesión; el ``commit`` único lo da el endpoint, así el
  par mutación+audit queda atómico (todo o nada) bajo ese commit.

Decisiones de diseño cerradas con producto (NO re-litigar), heredadas del endpoint:

(1) El dueño ve su memoria COMPLETA descifrada (se reusan los ``*Out`` sagrados; el
    blob cifrado nunca viaja). (2) La capa va en el PATH, no un ``/memory/{id}`` plano
    (evita el oráculo cross-tabla). (3) AISLAMIENTO sin oráculo: todo filtra por el
    ``user_id`` del JWT (ligado al ``__init__`` de cada store); una ref ajena da el
    MISMO 404 que una inexistente. (4) DECRYPT POST-OWNERSHIP: los stores filtran por
    ``id`` + ``user_id`` y devuelven ``None`` ANTES de descifrar si la fila no es del
    user. Regla #4: ni el recount ni el wipe ni el audit descifran ni logean contenido
    (solo enteros y digests sha256 viajan).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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

# Versión del formato de export (``MemoryExport.version``). Bump al evolucionar.
_EXPORT_VERSION = 1

# Top-N por capa semánticamente buscable (semantic + episodic) en ``search``.
_SEARCH_LIMIT_PER_LAYER = 10

# Score 0..1 por RANK (proxy de relevancia, contrato de presentación con el front:
# el reranker del store no expone su score crudo y la firma sagrada no se toca).
_SEARCH_SCORE_TOP = 0.95
_SEARCH_SCORE_STEP = 0.08
_SEARCH_SCORE_FLOOR = 0.5


# --- Excepciones de dominio (el router las mapea a status HTTP) ------------------


class MemoryServiceError(Exception):
    """Base de las señales de dominio del ``MemoryService``.

    El router captura ESTA base y la traduce a la ``HTTPException`` del contrato
    (status + detail); el service nunca conoce códigos HTTP.
    """


class MemoryItemNotFoundError(MemoryServiceError):
    """Ref inexistente o ajena → el router responde 404 con un detail uniforme.

    Sin oráculo de existencia ajena (regla de aislamiento): el store filtra por
    ``user_id`` y devuelve ``None`` para una fila de otro user, indistinguible de
    una inexistente.
    """


class InvalidMemoryRefError(MemoryServiceError):
    """La ``ref`` de semantic/episodic no parsea a UUID → el router responde 422.

    Espeja el 422 que daría un path param tipado ``UUID``; acá es manual porque la
    ref es polimórfica por capa (UUID en semantic/episodic, ``key`` en procedural).
    """


class EpisodicNotEditableError(MemoryServiceError):
    """PATCH sobre ``episodic`` → el router responde 405 Method Not Allowed.

    El ``summary`` lo genera el worker de consolidación; reescribir a mano "un
    resumen de lo que pasó" corrompe la trazabilidad. El dueño puede BORRAR un
    episodio (DELETE), no reescribirlo.
    """


class MemoryFieldRequiredError(MemoryServiceError):
    """El body del PATCH no trae el campo que la capa exige → el router responde 422.

    Lleva ``detail`` con el mensaje específico de la capa (semantic exige
    ``content``; procedural exige ``value``).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class WipeConfirmRequiredError(MemoryServiceError):
    """Execute del wipe sin el confirm per-layer → el router responde 422.

    El execute destructivo EXIGE la guarda de intención (el ``MemoryWipeConfirm``);
    el preview (``?dry_run=true``) no la pide.
    """


class WipeCountMismatchError(MemoryServiceError):
    """El confirm no matchea el recount actual → el router responde 409 Conflict.

    Lleva los conteos ACTUALES por capa + el total para que el cliente re-confirme
    con un preview fresco. NADA se borró ni se commiteó.
    """

    def __init__(self, *, semantic: int, episodic: int, procedural: int) -> None:
        super().__init__("wipe count mismatch")
        self.semantic = semantic
        self.episodic = episodic
        self.procedural = procedural
        self.total = semantic + episodic + procedural


# --- Helpers de presentación de la búsqueda (lógica pura, testeable aislada) -----


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


def _parse_uuid_ref(ref: str) -> UUID:
    """Parsea la ``ref`` polimórfica a UUID (semantic/episodic).

    Raises:
        InvalidMemoryRefError: si ``ref`` no es un UUID válido (el router → 422).
    """
    try:
        return UUID(ref)
    except ValueError as exc:
        raise InvalidMemoryRefError from exc


class MemoryService:
    """Orquesta la memoria privada de UN usuario (todas las ops de ``/v1/memory``).

    Construye el triplete de stores por-request ligado al ``user_id`` (semantic y
    episodic toman embedder + reranker; procedural no, no cifra ni embeddea — espeja
    el ``__init__`` sagrado sin tocarlo) más un ``AuditStore`` compartido para las
    mutaciones. El embedder/reranker viajan aunque el listado/export/wipe no
    embeddeen: es lo menos invasivo.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        embedder: EmbeddingClient,
        reranker: Reranker,
    ) -> None:
        self._session = session
        self._semantic = SemanticMemoryStore(session, user_id, embedder, reranker)
        self._episodic = EpisodicMemoryStore(session, user_id, embedder, reranker)
        self._procedural = ProceduralMemoryStore(session, user_id)
        self._audit_store = AuditStore(session, user_id)

    # --- Audit (centraliza el compute_record_hash + record de las mutaciones) ----

    async def _audit(
        self,
        *,
        operation: AuditOperation,
        target_layer: MemoryLayer,
        target_id: UUID | None,
        hash_source: str,
        sensitive: bool,
    ) -> None:
        """Escribe UNA fila de audit (issue #161) tras una mutación EFECTIVA.

        ``record_hash`` = sha256 de ``hash_source`` (regla #4: digest, nunca
        plaintext). ``origin_*`` quedan ``None``: acción del usuario por HTTP (sin
        LLM/tool), lo que distingue el audit de endpoint del de consolidación
        (``origin_model=QWEN``). La fila va en la MISMA sesión que la mutación, antes
        del único ``commit`` del endpoint → mutación + audit son atómicos.
        """
        await self._audit_store.record(
            operation=operation,
            target_layer=target_layer,
            target_id=target_id,
            record_hash=compute_record_hash(hash_source),
            sensitive=sensitive,
        )

    # --- Paginación por capa (helpers de ``list_grouped``) -----------------------

    async def _semantic_page(self, *, limit: int, offset: int) -> SemanticMemoryPage:
        """``SemanticMemoryPage``: ``items`` paginados + ``total`` del user.

        ``count`` + ``list_all`` NO son atómicos (dos statements bajo READ COMMITTED):
        si el worker inserta/borra entre ambos, ``total`` puede diferir de la página
        por ~1 fila. Es el trade-off ACEPTADO de toda paginación (staleness benigno,
        se reconcilia en el próximo fetch). El export usa ``list_all()`` sin ``count``.
        """
        items = await self._semantic.list_all(limit=limit, offset=offset)
        total = await self._semantic.count()
        # ``total or 0`` por consistencia con sessions.py (el COUNT da int acá; el
        # patrón uniforme de las *Page del repo blinda un None hipotético).
        return SemanticMemoryPage(items=items, total=total or 0)

    async def _episodic_page(self, *, limit: int, offset: int) -> EpisodicMemoryPage:
        """``EpisodicMemoryPage``: ``items`` paginados + ``total`` (TOCTOU benigno: ver arriba)."""
        items = await self._episodic.list_all(limit=limit, offset=offset)
        total = await self._episodic.count()
        return EpisodicMemoryPage(items=items, total=total or 0)

    async def _procedural_page(self, *, limit: int, offset: int) -> ProceduralMemoryPage:
        """``ProceduralMemoryPage``: ``items`` paginados en DB + ``total`` (TOCTOU benigno)."""
        items = await self._procedural.list_all(limit=limit, offset=offset)
        total = await self._procedural.count()
        # ``total or 0`` uniforme con _semantic_page/_episodic_page (el COUNT da int; el
        # patrón de las *Page del repo blinda un None hipotético).
        return ProceduralMemoryPage(items=items, total=total or 0)

    # --- Lecturas ----------------------------------------------------------------

    async def list_grouped(
        self,
        *,
        layer: MemoryLayer | None,
        limit: int,
        offset: int,
    ) -> MemoryGroupedResponse | SemanticMemoryPage | EpisodicMemoryPage | ProceduralMemoryPage:
        """Lista la memoria del user, opcionalmente filtrada por ``layer``.

        Sin ``layer``: respuesta AGRUPADA con las 3 capas (cada una su página +
        ``total``). Con ``layer``: solo la ``*Page`` de esa rama. No embeddea (es un
        listado, no una búsqueda).
        """
        if layer is MemoryLayer.SEMANTIC:
            return await self._semantic_page(limit=limit, offset=offset)
        if layer is MemoryLayer.EPISODIC:
            return await self._episodic_page(limit=limit, offset=offset)
        if layer is MemoryLayer.PROCEDURAL:
            return await self._procedural_page(limit=limit, offset=offset)

        return MemoryGroupedResponse(
            semantic=await self._semantic_page(limit=limit, offset=offset),
            episodic=await self._episodic_page(limit=limit, offset=offset),
            procedural=await self._procedural_page(limit=limit, offset=offset),
        )

    async def export_all(self) -> MemoryExport:
        """Las 3 capas COMPLETAS descifradas + ``version`` + ``exported_at``.

        Sin paginar (on-prem, pocos hechos por user) y en UN query por capa
        (``list_all`` sin ``limit`` trae todo): evita el ``count()``-para-el-limit y
        su TOCTOU. El router lo envuelve en un ``JSONResponse`` con header de descarga.
        """
        return MemoryExport(
            version=_EXPORT_VERSION,
            exported_at=datetime.now(UTC),
            semantic=await self._semantic.list_all(),
            episodic=await self._episodic.list_all(),
            procedural=await self._procedural.list_all(),
        )

    async def search(self, query: str) -> MemorySearchResponse:
        """Búsqueda semántica (hechos + momentos). ``query`` ya viene stripped y no vacío.

        Corre el pipeline del store (embed → ANN top-K → descifrar → rerank) sobre las
        capas semánticamente buscables, top-``_SEARCH_LIMIT_PER_LAYER`` por capa.
        Procedural NO entra (key-value, no embeddea). Regla #4: el ``snippet`` viaja
        descifrado (el store descifra in-process); el blob cifrado nunca entra.
        """
        semantic_results = await self._semantic.search(query, limit=_SEARCH_LIMIT_PER_LAYER)
        episodic_results = await self._episodic.search(query, limit=_SEARCH_LIMIT_PER_LAYER)
        return _build_search_response(query, semantic_results, episodic_results)

    async def get_item(
        self, *, layer: MemoryLayer, ref: str
    ) -> SemanticMemoryOut | EpisodicMemoryOut | ProceduralMemoryOut:
        """UN ítem por capa + referencia.

        Raises:
            InvalidMemoryRefError: ``ref`` no-UUID en semantic/episodic (router → 422).
            MemoryItemNotFoundError: ref inexistente o ajena (router → 404 uniforme).
        """
        if layer is MemoryLayer.PROCEDURAL:
            # Procedural: la ref es la ``key`` (str), no un UUID.
            proc_item = await self._procedural.get(ref)
            if proc_item is None:
                raise MemoryItemNotFoundError
            return proc_item

        memory_id = _parse_uuid_ref(ref)

        if layer is MemoryLayer.SEMANTIC:
            sem_item = await self._semantic.get_by_id(memory_id)
            if sem_item is None:
                raise MemoryItemNotFoundError
            return sem_item

        # layer is EPISODIC (las 3 ramas de MemoryLayer están cubiertas).
        epi_item = await self._episodic.get_by_id(memory_id)
        if epi_item is None:
            raise MemoryItemNotFoundError
        return epi_item

    # --- Mutaciones (flush vía store + audit; el commit lo da el endpoint) --------

    async def update_item(
        self, *, layer: MemoryLayer, ref: str, body: MemoryPatchRequest
    ) -> SemanticMemoryOut | ProceduralMemoryOut:
        """Edita UN ítem por capa. Mutación polimórfica + aislamiento estructural.

        - ``semantic``: actualiza ``content`` (re-embeddea + re-cifra). Audita el
          digest del nuevo content (sensitive=False).
        - ``procedural``: actualiza el ``value`` (JSONB) de una key EXISTENTE (UPDATE
          puro, NO upsert). Audita el digest del payload canónico (key, value).
        - ``episodic``: no se edita (``EpisodicNotEditableError`` → 405).

        Raises:
            EpisodicNotEditableError: PATCH episodic (router → 405).
            MemoryFieldRequiredError: el body no trae el campo de la capa (router → 422).
            InvalidMemoryRefError: ref no-UUID en semantic (router → 422).
            MemoryItemNotFoundError: ref inexistente o ajena (router → 404).
        """
        if layer is MemoryLayer.EPISODIC:
            raise EpisodicNotEditableError

        if layer is MemoryLayer.SEMANTIC:
            if body.content is None:
                raise MemoryFieldRequiredError("el PATCH semantic requiere 'content'")
            memory_id = _parse_uuid_ref(ref)
            sem_item = await self._semantic.update(memory_id, body.content)
            if sem_item is None:
                raise MemoryItemNotFoundError
            # Audit tras el UPDATE EFECTIVO (digest del nuevo content; semantic nunca
            # es sensible). Misma sesión que el update → atómicos por el commit del endpoint.
            await self._audit(
                operation=AuditOperation.UPDATE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=sem_item.id,
                hash_source=body.content,
                sensitive=False,
            )
            return sem_item

        # layer is PROCEDURAL: la ref es la ``key`` (str). Exige ``value`` (dict).
        if body.value is None:
            raise MemoryFieldRequiredError("el PATCH procedural requiere 'value'")
        proc_item = await self._procedural.update(ref, body.value)
        if proc_item is None:
            # Key inexistente o ajena: 404 (NUNCA se crea vía PATCH — eso sería upsert).
            raise MemoryItemNotFoundError
        await self._audit(
            operation=AuditOperation.UPDATE,
            target_layer=MemoryLayer.PROCEDURAL,
            target_id=proc_item.id,
            hash_source=procedural_hash_payload(ref, body.value),
            sensitive=False,
        )
        return proc_item

    async def delete_item(self, *, layer: MemoryLayer, ref: str) -> None:
        """Borra UN ítem por capa + referencia. Aislamiento estructural (filtra por user_id).

        Una ref ajena o inexistente devuelve ``False`` del store → ``MemoryItemNotFoundError``
        (404 uniforme, sin oráculo, sin tocar data ajena). Audita tras el DELETE EFECTIVO:
        epi marca ``sensitive=True`` (conservador, sin descifrar la capa sensible);
        semantic/procedural nunca son sensibles.

        Raises:
            InvalidMemoryRefError: ref no-UUID en semantic/episodic (router → 422).
            MemoryItemNotFoundError: ref inexistente o ajena (router → 404).
        """
        if layer is MemoryLayer.PROCEDURAL:
            # Procedural: la ref es la ``key`` (str). target_id=None (el delete-by-key no
            # retorna id; el record_hash de la key ata la fila a la entrada borrada).
            deleted = await self._procedural.delete(ref)
            if not deleted:
                raise MemoryItemNotFoundError
            await self._audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.PROCEDURAL,
                target_id=None,
                hash_source=ref,
                sensitive=False,
            )
            return

        memory_id = _parse_uuid_ref(ref)

        if layer is MemoryLayer.SEMANTIC:
            deleted = await self._semantic.delete(memory_id)
        else:
            # layer is EPISODIC (las 3 ramas de MemoryLayer están cubiertas).
            deleted = await self._episodic.delete(memory_id)

        if not deleted:
            raise MemoryItemNotFoundError
        # record_hash = sha256 del id (el contenido ya no existe; el id identifica la fila
        # borrada). sensitive=True SOLO para episodic (única capa sensible; se sobre-marca
        # sin descifrar — fail-safe para auditoría, consistente con el wipe episódico).
        await self._audit(
            operation=AuditOperation.DELETE,
            target_layer=layer,
            target_id=memory_id,
            hash_source=str(memory_id),
            sensitive=(layer is MemoryLayer.EPISODIC),
        )

    # --- Wipe total (preview read-only + execute destructivo) --------------------

    async def wipe_preview(self) -> MemoryWipePreview:
        """Cuenta las 3 capas del user (read-only, no muta ni descifra). Siempre válido.

        Un user sin memoria es un estado VÁLIDO (preview ``{0,0,0,0}``), jamás 404.
        Solo viajan enteros (regla #4).
        """
        sem_count = await self._semantic.count()
        epi_count = await self._episodic.count()
        proc_count = await self._procedural.count()
        return MemoryWipePreview(
            semantic=sem_count,
            episodic=epi_count,
            procedural=proc_count,
            total=sem_count + epi_count + proc_count,
        )

    async def wipe_execute(self, *, body: MemoryWipeConfirm | None) -> MemoryWipeResult:
        """Wipe TOTAL destructivo de las 3 capas, con guarda de intención.

        Flujo (atómico bajo el commit del endpoint): recuenta el estado ACTUAL; si el
        confirm per-layer no matchea → ``WipeCountMismatchError`` (409, nada se borra);
        si matchea → ``wipe()`` de las 3 capas (capturando el rowcount REAL) + una fila
        de audit por capa con borrado efectivo (rowcount > 0). El confirm es una guarda
        de INTENCIÓN, no cirugía exacta: el ``DELETE WHERE user_id`` barre el estado
        presente completo, así el receipt reporta el rowcount REAL.

        Raises:
            WipeConfirmRequiredError: execute sin ``body`` (router → 422).
            WipeCountMismatchError: el confirm no matchea el recount (router → 409).
        """
        # Recontar el estado ACTUAL de las 3 capas (en la misma transacción del wipe).
        sem_count = await self._semantic.count()
        epi_count = await self._episodic.count()
        proc_count = await self._procedural.count()

        if body is None:
            # Sin la guarda de intención no se ejecuta el destructivo (nada mutó).
            raise WipeConfirmRequiredError

        if (
            body.expected_semantic != sem_count
            or body.expected_episodic != epi_count
            or body.expected_procedural != proc_count
        ):
            # 409 con los conteos ACTUALES: el cliente re-confirma con un preview fresco.
            raise WipeCountMismatchError(
                semantic=sem_count, episodic=epi_count, procedural=proc_count
            )

        # Match: hard-delete de las 3 capas, capturando el rowcount REAL de cada una.
        sem_wiped = await self._semantic.wipe()
        epi_wiped = await self._episodic.wipe()
        proc_wiped = await self._procedural.wipe()

        # Una fila de audit por CADA capa con borrado EFECTIVO (rowcount > 0). El wipe es
        # DELETE-by-user masivo: target_id=None y el record_hash ata la fila a "el wipe de
        # esta capa" (sha256 de ``wipe:<capa>``). EPISODIC va sensitive=True conservador (el
        # wipe pudo arrasar episodios sensibles y no se chequea per-entry).
        if sem_wiped > 0:
            await self._audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.SEMANTIC,
                target_id=None,
                hash_source=f"wipe:{MemoryLayer.SEMANTIC.value}",
                sensitive=False,
            )
        if epi_wiped > 0:
            await self._audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.EPISODIC,
                target_id=None,
                hash_source=f"wipe:{MemoryLayer.EPISODIC.value}",
                sensitive=True,
            )
        if proc_wiped > 0:
            await self._audit(
                operation=AuditOperation.DELETE,
                target_layer=MemoryLayer.PROCEDURAL,
                target_id=None,
                hash_source=f"wipe:{MemoryLayer.PROCEDURAL.value}",
                sensitive=False,
            )

        return MemoryWipeResult(
            semantic=sem_wiped,
            episodic=epi_wiped,
            procedural=proc_wiped,
            total=sem_wiped + epi_wiped + proc_wiped,
        )
