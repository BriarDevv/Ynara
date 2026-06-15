"""Tools del namespace ``memory`` (M7).

``MemorySearchTool``  (``memory.search``),  ``MemoryAddTool``  (``memory.add``),
``MemoryUpdateTool`` (``memory.update``) y ``MemoryDeleteTool`` (``memory.delete``).

El ``user_id`` **nunca** viaja como argumento de la tool: el ``SemanticMemoryStore``
ya está ligado al ``user_id`` en su constructor (la key de cifrado se deriva de
``user_id``; pasarlo por argumento permitiría descifrar blobs de otro usuario).
Las tools reciben el store ya construido en ``memory_registry()``.

``memory.add`` NO escribe de forma síncrona (regla #2 de ``MEMORY.md``: la
escritura de memoria nunca va en el path de respuesta). Devuelve
``not_wired_result`` con el detalle de consolidación async pendiente (M8).

``memory.search`` cablea el store real: embed → ANN → descifrar → rerank.
``memory.update`` / ``memory.delete`` cablean el store (solo semántica).

Errores de validación → ``tool_error('invalid_arguments', first_validation_error(exc))``.
Nunca se propaga una excepción al modelo.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.tools.base import (
    first_validation_error,
    not_wired_result,
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


class _AddArgs(BaseModel):
    """Argumentos de ``memory.add``.

    ``layer`` sólo acepta ``'semantic'`` por ahora (Literal): episodic/procedural
    se escriben vía el pipeline async de M8.
    ``user_id`` ausente por diseño (el store ya está ligado a él).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    content: str
    layer: Literal["semantic"]
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

    NO escribe de forma síncrona (MEMORY.md regla #2: la escritura de memoria
    nunca va en el path de respuesta del agente). Devuelve ``not_wired_result``
    con el detalle de la consolidación async pendiente (M8).
    """

    name = f"{_NAMESPACE}.add"
    namespace = _NAMESPACE
    description = (
        "Registra un nuevo hecho en la memoria semántica del usuario "
        "(la escritura real es async — M8)."
    )

    def __init__(self, store: SemanticMemoryStore) -> None:
        self._store = store  # guardado aunque no se use (wiring completo en M8)

    @property
    def parameters(self) -> dict[str, object]:
        return tool_schema(_AddArgs)

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        try:
            validated = _AddArgs.model_validate(arguments)
        except ValidationError as exc:
            return tool_error("invalid_arguments", first_validation_error(exc))

        return not_wired_result(
            self.name,
            validated.model_dump(mode="json"),
            detail="consolidacion async pendiente (M8)",
        )


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
