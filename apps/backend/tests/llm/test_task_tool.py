"""Tests unitarios de las task tools REALES (Fase D1).

Sin DB ni red — puramente unitarios. Usan un ``FakeTaskStore`` que implementa la
misma interfaz que ``TaskStore`` sin tocar Postgres (mismo patrón que
``FakeCalendarStore`` en ``test_calendar_tool.py``).

Verifican:
- ``task.create_task`` con args válidos llama al store con un ``TaskCreate`` bien
  armado y devuelve el dict del store.
- Args inválidos (falta title, vacío, tipo incorrecto, extra, epoch numérico,
  duration <= 0 o > cap) -> ``invalid_arguments``, NUNCA propaga excepción.
- ``user_id`` no puede inyectarse por argumento (``extra='forbid'``).
- ``task.list_tasks`` devuelve ``{tasks}``.
- ``task_registry()`` arma un registry con las 2 tools en namespace ``task``.
- Los stubs ``CreateTaskTool`` / ``ListTasksTool`` (playground observado) SIGUEN
  siendo not_wired (no se rompió la invariante de no-efecto de ADR-019).
"""

from __future__ import annotations

import re
from typing import Any

from app.llm.tools.task import (
    AgentCreateTaskTool,
    AgentListTasksTool,
    CreateTaskTool,
    ListTasksTool,
    task_registry,
)
from app.schemas.task import TaskCreate

_VALID_SCHEDULE = "2026-06-22T15:00:00-03:00"


class FakeTaskStore:
    """Stub de ``TaskStore`` sin DB."""

    def __init__(
        self,
        *,
        create_result: dict[str, object] | None = None,
        list_result: list[dict[str, object]] | None = None,
    ) -> None:
        self._create_result = create_result or {"id": "task-fake", "title": "stub"}
        self._list_result = list_result or []
        self.create_calls: list[TaskCreate] = []
        self.list_calls: int = 0

    async def create_task(self, payload: TaskCreate) -> dict[str, object]:
        self.create_calls.append(payload)
        return self._create_result

    async def list_tasks(self) -> list[dict[str, object]]:
        self.list_calls += 1
        return self._list_result


# ---------------------------------------------------------------------------
# task.create_task (real)
# ---------------------------------------------------------------------------


class TestAgentCreateTask:
    async def test_valid_args_calls_store_with_task_create(self) -> None:
        store = FakeTaskStore(create_result={"id": "t-1", "title": "Dentista"})
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Dentista",
                "scheduled_at": _VALID_SCHEDULE,
                "duration_min": 15,
            }
        )

        assert "error" not in result
        assert result == {"id": "t-1", "title": "Dentista"}
        assert len(store.create_calls) == 1
        payload = store.create_calls[0]
        assert isinstance(payload, TaskCreate)
        assert payload.title == "Dentista"
        assert payload.duration_min == 15

    async def test_minimal_args_ok(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "Pendiente"})

        assert "error" not in result
        payload = store.create_calls[0]
        assert payload.scheduled_at is None
        assert payload.duration_min is None

    async def test_missing_title_returns_invalid_arguments(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"scheduled_at": _VALID_SCHEDULE})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_empty_title_returns_invalid_arguments(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": ""})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_non_positive_duration_returns_invalid_arguments(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "duration_min": 0})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_numeric_epoch_scheduled_at_rejected(self) -> None:
        # IsoDatetime rechaza epoch numérico (mismo endurecimiento que calendar).
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "scheduled_at": 1716000000})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_numeric_string_epoch_rejected(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "scheduled_at": "1716000000"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_user_id_arg_rejected(self) -> None:
        # user_id NO puede viajar como argumento (extra='forbid'): el store ya está
        # ligado al user_id; pasarlo permitiría crear tareas para otro usuario.
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"title": "x", "user_id": "00000000-0000-0000-0000-000000000000"}
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_title_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: title ≤ 200. Un título de 50KB no debe llegar al store.
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x" * 201})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_title_at_max_length_ok(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x" * 200})

        assert "error" not in result
        assert store.create_calls[0].title == "x" * 200

    async def test_duration_over_max_rejected(self) -> None:
        # Cota LLM-fed: duration_min ≤ 43200 (un mes en minutos).
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "duration_min": 43201})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_duration_at_max_ok(self) -> None:
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "duration_min": 43200})

        assert "error" not in result
        assert store.create_calls[0].duration_min == 43200

    async def test_error_message_does_not_leak_user_value(self) -> None:
        # regla #4: el mensaje no vuelca el valor recibido del usuario.
        store = FakeTaskStore()
        tool = AgentCreateTaskTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "scheduled_at": "secreto-del-usuario"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert "secreto-del-usuario" not in result["error"]["message"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# task.list_tasks (real)
# ---------------------------------------------------------------------------


class TestAgentListTasks:
    async def test_valid_args_calls_store_and_returns_tasks(self) -> None:
        store = FakeTaskStore(list_result=[{"id": "t-1"}, {"id": "t-2"}])
        tool = AgentListTasksTool(store)  # type: ignore[arg-type]

        result = await tool.execute({})

        assert "error" not in result
        assert result == {"tasks": [{"id": "t-1"}, {"id": "t-2"}]}
        assert store.list_calls == 1

    async def test_extra_arg_rejected(self) -> None:
        store = FakeTaskStore()
        tool = AgentListTasksTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"user_id": "x"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert store.list_calls == 0


# ---------------------------------------------------------------------------
# task_registry
# ---------------------------------------------------------------------------


class TestTaskRegistry:
    def test_registry_has_two_task_tools(self) -> None:
        store = FakeTaskStore()
        registry = task_registry(store)  # type: ignore[arg-type]

        specs = registry.specs_for(["task"])
        names = {s.name for s in specs}

        assert names == {"task.create_task", "task.list_tasks"}

    def test_registry_no_specs_without_task_namespace(self) -> None:
        store = FakeTaskStore()
        registry = task_registry(store)  # type: ignore[arg-type]

        assert registry.specs_for(["calendar"]) == []

    def test_all_specs_have_object_schema_without_docstring(self) -> None:
        store = FakeTaskStore()
        registry = task_registry(store)  # type: ignore[arg-type]

        for spec in registry.specs_for(["task"]):
            assert spec.parameters["type"] == "object"
            assert "properties" in spec.parameters
            assert "description" not in spec.parameters

    async def test_registry_execute_create_via_registry(self) -> None:
        store = FakeTaskStore(create_result={"id": "t-via-reg"})
        registry = task_registry(store)  # type: ignore[arg-type]

        result = await registry.execute("task.create_task", {"title": "x"})

        assert "error" not in result
        assert result == {"id": "t-via-reg"}

    def test_tool_names_are_snake_case_namespace_action(self) -> None:
        store = FakeTaskStore()
        registry = task_registry(store)  # type: ignore[arg-type]
        for spec in registry.specs_for(["task"]):
            assert re.match(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", spec.name), spec.name


# ---------------------------------------------------------------------------
# Invariante de no-efecto (ADR-019): los STUBS del default siguen not_wired
# ---------------------------------------------------------------------------


class TestStubsStillNotWired:
    """Fase D1 NO debe romper la invariante de no-efecto del playground observado.

    ``CreateTaskTool`` / ``ListTasksTool`` (los del ``default_registry()``) deben
    seguir devolviendo ``not_wired`` (stubs sin efecto), independientes de las tools
    reales.
    """

    async def test_stub_create_task_still_not_wired(self) -> None:
        result = await CreateTaskTool().execute({"title": "x"})
        assert result["status"] == "not_wired"

    async def test_stub_list_tasks_still_not_wired(self) -> None:
        result = await ListTasksTool().execute({})
        assert result["status"] == "not_wired"

    async def test_stub_create_task_validates_args(self) -> None:
        # El stub también valida (epoch numérico en due rechazado, mismo endurecimiento).
        result: dict[str, Any] = await CreateTaskTool().execute({"title": "x", "due": 1716000000})
        assert result["error"]["code"] == "invalid_arguments"
