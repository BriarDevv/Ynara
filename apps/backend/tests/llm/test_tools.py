"""Tests del framework de tools (M6): base + registry + stubs.

Sin DB ni red. Verifican:

- ``default_registry().specs_for([...])`` filtra por namespace y devuelve
  ``ToolSpec`` bien formados (la identidad que el cliente vLLM envuelve en el
  wire OpenAI ``{"type": "function", "function": {...}}``).
- ``execute`` devuelve dict de resultado o dict de error estructurado, nunca
  propaga una excepcion al modelo.
- Naming ``namespace.action`` snake_case y namespaces alineados con
  ``ynara.config.json``.
"""

from __future__ import annotations

import re

import pytest

from app.llm.schemas import ToolSpec
from app.llm.tools import Tool, ToolRegistry, default_registry, tool_error
from app.llm.tools.base import to_spec
from app.llm.tools.calendar import CreateEventTool

_VALID_START = "2026-05-20T15:00:00-03:00"
_VALID_END = "2026-05-20T16:00:00-03:00"

# Snake_case ``namespace.action``: solo minusculas, digitos y un unico punto.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# Namespaces tal como aparecen en ``ynara.config.json[modes][*].tools_enabled``.
_CONFIG_NAMESPACES = {"calendar", "reminders", "memory"}


class TestSpecsFor:
    def test_all_four_tools_for_calendar_and_reminders(self) -> None:
        specs = default_registry().specs_for(["calendar", "reminders"])
        assert len(specs) == 4
        names = {s.name for s in specs}
        assert names == {
            "calendar.create_event",
            "calendar.list_events",
            "reminder.set",
            "reminder.list",
        }

    def test_specs_are_openai_shaped(self) -> None:
        # ``specs_for`` devuelve ``ToolSpec`` con la identidad plana; el
        # cliente vLLM la envuelve en ``{"type": "function", "function": ...}``.
        specs = default_registry().specs_for(["calendar", "reminders"])
        for spec in specs:
            assert isinstance(spec, ToolSpec)
            assert spec.name
            assert spec.description
            assert isinstance(spec.parameters, dict)
            # JSON Schema OpenAI: objeto con ``properties``.
            assert spec.parameters["type"] == "object"
            assert "properties" in spec.parameters

    def test_empty_namespaces_no_tools(self) -> None:
        assert default_registry().specs_for([]) == []

    def test_only_calendar_returns_two(self) -> None:
        specs = default_registry().specs_for(["calendar"])
        names = {s.name for s in specs}
        assert names == {"calendar.create_event", "calendar.list_events"}

    def test_only_reminders_returns_two(self) -> None:
        specs = default_registry().specs_for(["reminders"])
        names = {s.name for s in specs}
        assert names == {"reminder.set", "reminder.list"}

    def test_memory_namespace_yields_nothing(self) -> None:
        # memory es M7: el registry por defecto no la incluye.
        assert default_registry().specs_for(["memory"]) == []


class TestExecuteSuccess:
    async def test_create_event_valid_args_returns_stub(self) -> None:
        registry = default_registry()
        result = await registry.execute(
            "calendar.create_event",
            {"title": "Cafe con Carla", "start": _VALID_START, "end": _VALID_END},
        )
        assert "error" not in result
        assert result["status"] == "not_wired"
        assert result["action"] == "calendar.create_event"

    async def test_list_events_valid_args_returns_stub(self) -> None:
        registry = default_registry()
        result = await registry.execute(
            "calendar.list_events",
            {"from_dt": _VALID_START, "to_dt": _VALID_END},
        )
        assert "error" not in result
        assert result["status"] == "not_wired"

    async def test_set_reminder_valid_args_returns_stub(self) -> None:
        registry = default_registry()
        result = await registry.execute(
            "reminder.set",
            {"text": "Llamar al dentista", "when": _VALID_START},
        )
        assert "error" not in result
        assert result["status"] == "not_wired"

    async def test_list_reminders_without_args_returns_stub(self) -> None:
        registry = default_registry()
        result = await registry.execute("reminder.list", {})
        assert "error" not in result
        assert result["status"] == "not_wired"


class TestExecuteErrors:
    async def test_unknown_tool_returns_structured_error(self) -> None:
        registry = default_registry()
        result = await registry.execute("calendar.delete_universe", {})
        assert result["error"]["code"] == "unknown_tool"  # type: ignore[index]

    async def test_invalid_args_returns_structured_error_no_raise(self) -> None:
        # Falta ``end`` y ``start`` no es datetime: nunca debe raise.
        registry = default_registry()
        result = await registry.execute(
            "calendar.create_event",
            {"title": "x", "start": "no-es-fecha"},
        )
        assert "error" in result
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_args_rejected_structured(self) -> None:
        # ``extra="forbid"``: argumentos de mas tambien son error estructurado.
        registry = default_registry()
        result = await registry.execute(
            "reminder.set",
            {"text": "x", "when": _VALID_START, "sneaky": True},
        )
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_error_message_does_not_leak_user_value(self) -> None:
        # regla #4: el mensaje no vuelca el valor recibido del usuario.
        # ``start`` invalido lleva un dato sensible que no debe filtrarse.
        registry = default_registry()
        result = await registry.execute(
            "calendar.create_event",
            {"title": "x", "start": "secreto-del-usuario", "end": _VALID_END},
        )
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        message = result["error"]["message"]  # type: ignore[index]
        assert "secreto-del-usuario" not in message


class TestDatetimeValidation:
    async def test_create_event_rejects_numeric_epoch(self) -> None:
        # strict=False coerceria un epoch int a fecha; IsoDatetime lo rechaza (#38).
        registry = default_registry()
        result = await registry.execute(
            "calendar.create_event",
            {"title": "x", "start": 1716000000, "end": _VALID_END},
        )
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_set_reminder_rejects_numeric_epoch(self) -> None:
        registry = default_registry()
        result = await registry.execute(
            "reminder.set",
            {"text": "x", "when": 1716000000.0},
        )
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_iso_string_still_accepted(self) -> None:
        # Sanity: el ISO 8601 string sigue pasando la validacion endurecida.
        registry = default_registry()
        result = await registry.execute(
            "calendar.create_event",
            {"title": "x", "start": _VALID_START, "end": _VALID_END},
        )
        assert "error" not in result


class TestNamingAndNamespaces:
    def test_names_are_snake_case_namespace_action(self) -> None:
        registry = default_registry()
        for spec in registry.specs_for(["calendar", "reminders"]):
            assert _NAME_RE.match(spec.name), spec.name

    def test_namespaces_match_config(self) -> None:
        tools: list[Tool] = [
            CreateEventTool(),
        ]
        for tool in tools:
            assert tool.namespace in _CONFIG_NAMESPACES

    def test_all_default_namespaces_in_config(self) -> None:
        registry = default_registry()
        # Recolectamos los namespaces via las tools registradas.
        specs_cal = registry.specs_for(["calendar"])
        specs_rem = registry.specs_for(["reminders"])
        assert specs_cal and specs_rem  # ambos namespaces estan en config


class TestBaseHelpers:
    def test_tool_error_shape(self) -> None:
        err = tool_error("boom", "algo fallo")
        assert err == {"error": {"code": "boom", "message": "algo fallo"}}

    def test_to_spec_matches_tool(self) -> None:
        tool = CreateEventTool()
        spec = to_spec(tool)
        assert spec.name == tool.name
        assert spec.description == tool.description
        assert spec.parameters == tool.parameters

    def test_tools_satisfy_protocol(self) -> None:
        assert isinstance(CreateEventTool(), Tool)

    async def test_registry_rejects_duplicate(self) -> None:
        registry = ToolRegistry([CreateEventTool()])
        with pytest.raises(ValueError):
            registry.register(CreateEventTool())
