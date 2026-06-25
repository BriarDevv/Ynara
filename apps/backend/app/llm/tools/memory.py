"""Tools del namespace ``memory`` (M7).

``MemorySearchTool``  (``memory.search``),  ``MemoryAddTool``  (``memory.add``),
``MemoryUpdateTool`` (``memory.update``) y ``MemoryDeleteTool`` (``memory.delete``).

El ``user_id`` **nunca** viaja como argumento de la tool: el ``SemanticMemoryStore``
ya está ligado al ``user_id`` en su constructor (la key de cifrado se deriva de
``user_id``; pasarlo por argumento permitiría descifrar blobs de otro usuario).
Las tools reciben el store ya construido en ``memory_registry()``.

``memory.add`` NO escribe de forma síncrona (regla #2 de ``MEMORY.md``: la
escritura de memoria nunca va en el path de respuesta). Acusa recibo en lenguaje
natural para el modelo; la escritura REAL la hace el worker de consolidación del
turno (``app/workflows/consolidation.py``, que ``ChatService`` encola post-commit).

``memory.search`` cablea el store real: embed → ANN → descifrar → rerank.
``memory.update`` / ``memory.delete`` cablean el store (solo semántica).

Errores de validación → ``tool_error('invalid_arguments', first_validation_error(exc))``.
Nunca se propaga una excepción al modelo.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from app.llm.tools.base import (
    first_validation_error,
    tool_error,
    tool_schema,
)
from app.llm.tools.registry import ToolRegistry
from app.memory.semantic import SemanticMemoryStore
from app.schemas.memory import SemanticMemoryOut

_NAMESPACE = "memory"


# ---------------------------------------------------------------------------
# Modelos de argumentos (strict=True, extra='forbid')
# ---------------------------------------------------------------------------


class _SearchArgs(BaseModel):
    """Argumentos de ``memory.search``."""

    model_config = ConfigDict(strict=True, extra="forbid")

    query: str
    limit: int = Field(5, ge=1, le=20)


def _coerce_layer_to_semantic(value: object) -> str:
    """Normaliza cualquier ``layer`` a ``'semantic'`` (única capa soportada hoy).

    ``memory.add`` sólo escribe semantic por ahora (episodic/procedural se escriben
    vía el pipeline async de M8). Un modelo chico (Qwen) alucina valores de ``layer``
    ('personal', 'base', ...) o pide capas aún no cableadas (episodic/procedural); con
    un ``Literal['semantic']`` estricto eso fallaba con ``invalid_arguments``, lo que
    hacía que el AGENTE le reportara al usuario un FALSO 'no pude guardar' aunque la
    escritura real es async (la hace el worker de consolidación, NO esta tool, que es
    un stub ``not_wired``). Coercionar a 'semantic' evita ese falso fallo. Cuando M8
    cablee multi-capa, ``layer`` vuelve a ser un ``Literal`` real con las 3 capas y
    esta función se restringe a aceptar SOLO strings (rechazando ``None``/``int``), que
    hoy también se coercionan en silencio porque la tool es no-op: post-M8 ese laxismo
    podría enmascarar un bug del prompt o del pipeline de tool-calling.
    """
    return "semantic"


class _AddArgs(BaseModel):
    """Argumentos de ``memory.add``.

    ``layer`` es opcional (default ``'semantic'``) y TOLERANTE: cualquier valor que el
    modelo mande se normaliza a ``'semantic'`` (ver ``_coerce_layer_to_semantic``), la
    única capa que esta tool soporta hoy. El schema sigue anunciando ``'semantic'`` para
    guiar al modelo, pero un valor alucinado ya no rompe el turno.
    ``extra='forbid'`` se mantiene: ``user_id`` (u otro campo) NO puede inyectarse por
    argumento (el store ya está ligado al ``user_id``; pasarlo permitiría apuntar a otro
    usuario). Un extra desconocido sigue siendo ``invalid_arguments``.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    content: str
    layer: Annotated[Literal["semantic"], BeforeValidator(_coerce_layer_to_semantic)] = "semantic"
    importance: int | None = Field(None, ge=0, le=100)


class _UpdateArgs(BaseModel):
    """Argumentos de ``memory.update``."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    content: str


class _DeleteArgs(BaseModel):
    """Argumentos de ``memory.delete``."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _project_memory_result(r: SemanticMemoryOut) -> dict[str, object]:
    """Proyecta un ``SemanticMemoryOut`` al shape que el modelo puede ver.

    Incluye solo ``{id, content, importance}`` (+ ``score`` si existe),
    omitiendo ``user_id``, ``source_session_id``, ``created_at`` y
    ``updated_at``. El ``id`` se mantiene para que memory.update/delete
    puedan identificar el recuerdo. Los UUIDs internos y timestamps no se
    exponen al modelo (evita regurgitacion de datos internos).

    Args:
        r: El ``SemanticMemoryOut`` a proyectar.

    Returns:
        Dict con las claves proyectadas, serializado con ``str`` para UUIDs.
    """
    projected: dict[str, object] = {
        "id": str(r.id),
        "content": r.content,
        "importance": r.importance,
    }
    # ``score`` no es un campo de SemanticMemoryOut hoy; queda como forward-compat
    # para cuando el reranker real anote relevancia (getattr defensivo).
    score = getattr(r, "score", None)
    if score is not None:
        projected["score"] = score
    return projected


class MemorySearchTool:
    """Busca en la memoria semántica del usuario.

    Pipeline: embed(query) → ANN pgvector HNSW cosine → descifrar → rerank
    (passthrough en M7) → devolver resultados proyectados al modelo.

    El resultado proyecta solo ``{id, content, importance}`` (+ ``score`` si
    existe), omitiendo ``user_id``, ``source_session_id``, ``created_at`` y
    ``updated_at`` para no exponer UUIDs internos al modelo.
    """

    name = f"{_NAMESPACE}.search"
    namespace = _NAMESPACE
    description = "Busca recuerdos relevantes en la memoria semántica del usuario."

    def __init__(self, store: SemanticMemoryStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_SearchArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _SearchArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        results = await self._store.search(validated.query, limit=validated.limit)
        return {
            "results": [_project_memory_result(r) for r in results],
        }


class MemoryAddTool:
    """Registra un hecho nuevo en la memoria del usuario.

    NO escribe de forma síncrona (MEMORY.md regla #2: la escritura de memoria nunca
    va en el path de respuesta del agente). La escritura REAL la hace el worker de
    consolidación (``app/workflows/consolidation.py``), que ``ChatService`` encola
    DESPUÉS del commit del turno de memoria. Esta tool solo ACUSA RECIBO para el
    modelo, en lenguaje natural.

    Antes devolvía un stub ``not_wired`` con jerga interna
    (``"consolidacion async pendiente (M8)"``): Qwen lo leía como una FALLA y le
    reportaba al usuario un falso "hubo un error ejecutando la acción". El acuse de
    recibo en prosa natural evita eso (el modelo confirma "listo, lo voy a recordar").
    """

    name = f"{_NAMESPACE}.add"
    namespace = _NAMESPACE
    description = (
        "Registra un nuevo hecho en la memoria del usuario (se consolida en segundo plano)."
    )

    def __init__(self, store: SemanticMemoryStore) -> None:
        self._store = store  # ligado aunque la escritura síncrona no use el store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AddArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            _AddArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        # Acuse de recibo OPACO para el modelo: status de éxito + un detail corto SIN
        # jerga de implementación. La escritura real es async (el worker de
        # consolidación del turno, encolado por ChatService), pero ese mecanismo NO
        # debe filtrarse a la respuesta del modelo (VOICE: "no narrás lo que hacés por
        # dentro"). Así qwen confirma natural ("listo, lo anoté") sin mencionar
        # "consolidación"/"segundo plano" ni inventar una falla.
        return {
            "status": "ok",
            "action": self.name,
            "detail": "Anotado en tu memoria.",
        }


class MemoryUpdateTool:
    """Actualiza el contenido de un recuerdo existente.

    Re-embeddea + re-cifra el hecho. Si el ``id`` no existe o pertenece a otro
    usuario, devuelve ``tool_error('not_found', ...)``.

    El resultado se proyecta con ``_project_memory_result`` (igual que
    ``memory.search``): solo ``{id, content, importance}``, omitiendo
    ``user_id``, ``source_session_id`` y timestamps — el modelo NUNCA ve UUIDs
    internos ni metadata de provenance (regla #4).
    """

    name = f"{_NAMESPACE}.update"
    namespace = _NAMESPACE
    description = "Actualiza el contenido de un recuerdo en la memoria semántica del usuario."

    def __init__(self, store: SemanticMemoryStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_UpdateArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _UpdateArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        try:
            memory_id = UUID(validated.id)
        except ValueError:
            return tool_error("invalid_arguments", "argumento invalido en 'id': uuid_parsing")

        result = await self._store.update(memory_id, validated.content)
        if result is None:
            return tool_error("not_found", f"memoria '{validated.id}' no encontrada")
        # Proyectar (igual que memory.search): el modelo NUNCA ve user_id,
        # source_session_id ni timestamps (regla #4). Antes esto devolvia el
        # model_dump completo y filtraba esa metadata interna al LLM.
        return _project_memory_result(result)


class MemoryDeleteTool:
    """Elimina físicamente un recuerdo de la memoria semántica.

    Si el ``id`` no existe o pertenece a otro usuario, devuelve
    ``tool_error('not_found', ...)``.
    """

    name = f"{_NAMESPACE}.delete"
    namespace = _NAMESPACE
    description = "Elimina un recuerdo de la memoria semántica del usuario."

    def __init__(self, store: SemanticMemoryStore) -> None:
        self._store = store

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_DeleteArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _DeleteArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        try:
            memory_id = UUID(validated.id)
        except ValueError:
            return tool_error("invalid_arguments", "argumento invalido en 'id': uuid_parsing")

        deleted = await self._store.delete(memory_id)
        if not deleted:
            return tool_error("not_found", f"memoria '{validated.id}' no encontrada")
        return {"deleted": True, "id": validated.id}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def memory_registry(semantic_store: SemanticMemoryStore) -> ToolRegistry:
    """Registry con las 4 memory tools ligadas a ``semantic_store``.

    NO toca ``default_registry()``: se construye aparte y se combina en el
    router (M8) cuando la memoria esté habilitada para el modo activo.
    """
    return ToolRegistry(
        [
            MemorySearchTool(semantic_store),
            MemoryAddTool(semantic_store),
            MemoryUpdateTool(semantic_store),
            MemoryDeleteTool(semantic_store),
        ]
    )
