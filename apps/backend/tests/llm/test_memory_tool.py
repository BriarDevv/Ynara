"""Tests unitarios de la tool ``memory.*`` (M7).

Sin DB ni red — puramente unitarios. Usan un ``FakeSemanticStore`` que
implementa la misma interfaz que ``SemanticMemoryStore`` sin tocar Postgres.

Verifican:
- ``memory.search`` con args validos llama al store y devuelve resultados.
- ``memory.add`` devuelve siempre ``not_wired`` (MEMORY.md regla #2).
- ``layer='episodic'`` es ``invalid_arguments`` (Literal).
- Args invalidos (falta campo, tipo incorrecto, extra) -> ``invalid_arguments``.
- ``memory.update`` / ``memory.delete`` con store que devuelve None/False -> ``not_found``.
- ``memory_registry()`` construye un registry con las 4 tools en namespace ``memory``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.llm.tools.memory import (
    MemoryAddTool,
    MemoryDeleteTool,
    MemorySearchTool,
    MemoryUpdateTool,
    memory_registry,
)
from app.schemas.memory import SemanticMemoryOut

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_USER_ID = uuid4()
_MEM_ID = uuid4()

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _make_out(
    content: str = "recuerdo de prueba",
    memory_id: UUID | None = None,
) -> SemanticMemoryOut:
    return SemanticMemoryOut(
        id=memory_id or _MEM_ID,
        user_id=_USER_ID,
        content=content,
        importance=50,
        source_session_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


class FakeSemanticStore:
    """Stub de ``SemanticMemoryStore`` sin DB."""

    def __init__(
        self,
        *,
        search_results: list[SemanticMemoryOut] | None = None,
        update_result: SemanticMemoryOut | None = None,
        delete_result: bool = True,
    ) -> None:
        self._search_results = search_results or []
        self._update_result = update_result
        self._delete_result = delete_result

        # Registro de llamadas para asserts
        self.search_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    async def search(self, query: str, limit: int = 5) -> list[SemanticMemoryOut]:
        self.search_calls.append({"query": query, "limit": limit})
        return self._search_results[:limit]

    async def update(self, memory_id: UUID, content: str) -> SemanticMemoryOut | None:
        self.update_calls.append({"memory_id": memory_id, "content": content})
        return self._update_result

    async def delete(self, memory_id: UUID) -> bool:
        self.delete_calls.append({"memory_id": memory_id})
        return self._delete_result


# ---------------------------------------------------------------------------
# memory.search
# ---------------------------------------------------------------------------


class TestMemorySearch:
    async def test_valid_args_calls_store_and_returns_results(self) -> None:
        out = _make_out("hecho semántico A")
        store = FakeSemanticStore(search_results=[out])
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "hecho A", "limit": 3})

        assert "error" not in result
        assert "results" in result
        assert len(result["results"]) == 1  # type: ignore[arg-type]
        assert store.search_calls[0] == {"query": "hecho A", "limit": 3}

    async def test_default_limit_is_five(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        await tool.execute({"query": "test"})

        assert store.search_calls[0]["limit"] == 5

    async def test_results_are_json_serializable(self) -> None:
        out = _make_out()
        store = FakeSemanticStore(search_results=[out])
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "q"})
        first = result["results"][0]  # type: ignore[index]

        # id debe estar presente y ser string
        assert isinstance(first["id"], str)
        assert first["content"] == "recuerdo de prueba"
        assert isinstance(first["importance"], int)
        # user_id, source_session_id, created_at, updated_at NO deben exponerse al modelo
        assert "user_id" not in first
        assert "source_session_id" not in first
        assert "created_at" not in first
        assert "updated_at" not in first

    async def test_missing_query_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"limit": 5})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_limit_too_high_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "test", "limit": 100})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_limit_zero_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "test", "limit": 0})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_arg_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "test", "user_id": "alguien"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_wrong_type_limit_returns_invalid_arguments(self) -> None:
        # strict=True: int estricto, no coerce string -> int
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "test", "limit": "cinco"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_error_message_does_not_leak_user_value(self) -> None:
        store = FakeSemanticStore()
        tool = MemorySearchTool(store)

        result = await tool.execute({"query": "test", "limit": "secreto"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert "secreto" not in result["error"]["message"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# memory.add — siempre not_wired (MEMORY.md regla #2)
# ---------------------------------------------------------------------------


class TestMemoryAdd:
    async def test_valid_args_returns_not_wired(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"content": "nuevo hecho", "layer": "semantic"})

        assert result["status"] == "not_wired"
        assert result["action"] == "memory.add"
        assert "consolidacion async" in result["detail"]  # type: ignore[operator]

    async def test_not_wired_does_not_call_store(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        await tool.execute({"content": "x", "layer": "semantic"})

        # memory.add nunca escribe síncrono
        assert not hasattr(store, "add_calls")

    async def test_with_importance_returns_not_wired(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute(
            {"content": "hecho importante", "layer": "semantic", "importance": 80}
        )

        assert result["status"] == "not_wired"

    async def test_layer_episodic_returns_invalid_arguments(self) -> None:
        # Literal['semantic']: 'episodic' debe rechazarse
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"content": "algo", "layer": "episodic"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_layer_procedural_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"content": "algo", "layer": "procedural"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_missing_content_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"layer": "semantic"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_missing_layer_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"content": "algo"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_importance_out_of_range_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute({"content": "algo", "layer": "semantic", "importance": 200})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_arg_user_id_returns_invalid_arguments(self) -> None:
        # user_id no debe viajar como argumento (extra='forbid')
        store = FakeSemanticStore()
        tool = MemoryAddTool(store)

        result = await tool.execute(
            {"content": "algo", "layer": "semantic", "user_id": str(_USER_ID)}
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]


# ---------------------------------------------------------------------------
# memory.update
# ---------------------------------------------------------------------------


class TestMemoryUpdate:
    async def test_valid_id_and_content_calls_store(self) -> None:
        mem_id = uuid4()
        out = _make_out("actualizado", memory_id=mem_id)
        store = FakeSemanticStore(update_result=out)
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"id": str(mem_id), "content": "actualizado"})

        assert "error" not in result
        assert result["content"] == "actualizado"  # type: ignore[index]
        assert store.update_calls[0]["memory_id"] == mem_id
        # Proyeccion (regla #4): el modelo ve solo {id, content, importance}, NUNCA
        # user_id, source_session_id ni timestamps (mismo contrato que memory.search).
        assert result["id"] == str(mem_id)  # type: ignore[index]
        assert "importance" in result
        assert "user_id" not in result
        assert "source_session_id" not in result
        assert "created_at" not in result
        assert "updated_at" not in result

    async def test_store_returns_none_yields_not_found(self) -> None:
        store = FakeSemanticStore(update_result=None)
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"id": str(uuid4()), "content": "x"})

        assert result["error"]["code"] == "not_found"  # type: ignore[index]

    async def test_invalid_uuid_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"id": "no-es-uuid", "content": "x"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_missing_content_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"id": str(uuid4())})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_missing_id_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"content": "algo"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_arg_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryUpdateTool(store)

        result = await tool.execute({"id": str(uuid4()), "content": "algo", "importance": 50})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]


# ---------------------------------------------------------------------------
# memory.delete
# ---------------------------------------------------------------------------


class TestMemoryDelete:
    async def test_valid_id_calls_store_and_returns_deleted(self) -> None:
        mem_id = uuid4()
        store = FakeSemanticStore(delete_result=True)
        tool = MemoryDeleteTool(store)

        result = await tool.execute({"id": str(mem_id)})

        assert "error" not in result
        assert result["deleted"] is True  # type: ignore[index]
        assert store.delete_calls[0]["memory_id"] == mem_id

    async def test_store_returns_false_yields_not_found(self) -> None:
        store = FakeSemanticStore(delete_result=False)
        tool = MemoryDeleteTool(store)

        result = await tool.execute({"id": str(uuid4())})

        assert result["error"]["code"] == "not_found"  # type: ignore[index]

    async def test_invalid_uuid_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryDeleteTool(store)

        result = await tool.execute({"id": "no-es-uuid"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_missing_id_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryDeleteTool(store)

        result = await tool.execute({})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_arg_returns_invalid_arguments(self) -> None:
        store = FakeSemanticStore()
        tool = MemoryDeleteTool(store)

        result = await tool.execute({"id": str(uuid4()), "user_id": str(_USER_ID)})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]


# ---------------------------------------------------------------------------
# memory_registry
# ---------------------------------------------------------------------------


class TestMemoryRegistry:
    def test_registry_has_four_memory_tools(self) -> None:
        store = FakeSemanticStore()
        registry = memory_registry(store)  # type: ignore[arg-type]

        specs = registry.specs_for(["memory"])
        names = {s.name for s in specs}

        assert names == {
            "memory.search",
            "memory.add",
            "memory.update",
            "memory.delete",
        }

    def test_registry_no_specs_without_memory_namespace(self) -> None:
        store = FakeSemanticStore()
        registry = memory_registry(store)  # type: ignore[arg-type]

        assert registry.specs_for(["calendar"]) == []

    def test_all_specs_have_object_schema(self) -> None:
        store = FakeSemanticStore()
        registry = memory_registry(store)  # type: ignore[arg-type]

        for spec in registry.specs_for(["memory"]):
            assert spec.parameters["type"] == "object"
            assert "properties" in spec.parameters

    def test_schemas_omit_model_docstring(self) -> None:
        store = FakeSemanticStore()
        registry = memory_registry(store)  # type: ignore[arg-type]

        for spec in registry.specs_for(["memory"]):
            assert "description" not in spec.parameters

    async def test_registry_execute_search_via_registry(self) -> None:
        out = _make_out("via registry")
        store = FakeSemanticStore(search_results=[out])
        registry = memory_registry(store)  # type: ignore[arg-type]

        result = await registry.execute("memory.search", {"query": "test"})

        assert "error" not in result
        assert len(result["results"]) == 1  # type: ignore[arg-type]

    async def test_registry_execute_unknown_tool_returns_error(self) -> None:
        store = FakeSemanticStore()
        registry = memory_registry(store)  # type: ignore[arg-type]

        result = await registry.execute("memory.unknown", {})

        assert result["error"]["code"] == "unknown_tool"  # type: ignore[index]

    @pytest.mark.parametrize(
        "name",
        ["memory.search", "memory.add", "memory.update", "memory.delete"],
    )
    def test_tool_name_format(self, name: str) -> None:
        import re

        assert re.match(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", name)
