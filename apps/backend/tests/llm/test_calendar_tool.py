"""Tests unitarios de las calendar tools REALES (Fase E, ADR-021).

Sin DB ni red — puramente unitarios. Usan un ``FakeCalendarStore`` que implementa
la misma interfaz que ``CalendarEventStore`` sin tocar Postgres (mismo patrón que
``FakeSemanticStore`` en ``test_memory_tool.py``).

Verifican:
- ``calendar.create_event`` con args válidos llama al store con un ``EventCreate``
  bien armado y devuelve el dict del store.
- Args inválidos (falta campo, tipo incorrecto, extra, epoch numérico, recurrence
  sin time_zone) -> ``invalid_arguments``, NUNCA propaga excepción.
- ``user_id`` no puede inyectarse por argumento (``extra='forbid'``).
- ``calendar.list_events`` con args válidos llama al store y devuelve ``{events}``.
- ``calendar_registry()`` arma un registry con las 2 tools en namespace ``calendar``.
- Los stubs ``CreateEventTool`` / ``ListEventsTool`` (playground observado) SIGUEN
  siendo not_wired (no se rompió la invariante de no-efecto de ADR-019).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.enums import Mode
from app.llm.tools.calendar import (
    AgentCreateEventTool,
    AgentListEventsTool,
    CreateEventTool,
    ListEventsTool,
    calendar_registry,
)
from app.schemas.calendar_event import EventCreate

_VALID_START = "2026-06-22T15:00:00-03:00"
_VALID_END = "2026-06-22T16:00:00-03:00"


class FakeCalendarStore:
    """Stub de ``CalendarEventStore`` sin DB."""

    def __init__(
        self,
        *,
        create_result: dict[str, object] | None = None,
        list_result: list[dict[str, object]] | None = None,
    ) -> None:
        self._create_result = create_result or {"id": "ev-fake", "title": "stub"}
        self._list_result = list_result or []
        self.create_calls: list[EventCreate] = []
        self.list_calls: list[dict[str, Any]] = []

    async def create_event(self, payload: EventCreate) -> dict[str, object]:
        self.create_calls.append(payload)
        return self._create_result

    async def list_events(self, from_dt: datetime, to_dt: datetime) -> list[dict[str, object]]:
        self.list_calls.append({"from_dt": from_dt, "to_dt": to_dt})
        return self._list_result


# ---------------------------------------------------------------------------
# calendar.create_event (real)
# ---------------------------------------------------------------------------


class TestAgentCreateEvent:
    async def test_valid_args_calls_store_with_event_create(self) -> None:
        store = FakeCalendarStore(create_result={"id": "ev-1", "title": "Reunión"})
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Reunión",
                "start_at": _VALID_START,
                "duration_min": 45,
                "location": "Oficina",
            }
        )

        assert "error" not in result
        assert result == {"id": "ev-1", "title": "Reunión"}
        # El store recibe un EventCreate de dominio con los campos correctos.
        assert len(store.create_calls) == 1
        payload = store.create_calls[0]
        assert isinstance(payload, EventCreate)
        assert payload.title == "Reunión"
        assert payload.duration_min == 45
        assert payload.location == "Oficina"

    async def test_minimal_args_ok(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"title": "Mínimo", "start_at": _VALID_START, "duration_min": 30}
        )

        assert "error" not in result
        payload = store.create_calls[0]
        assert payload.mode is None
        assert payload.location is None

    async def test_all_day_event_is_created(self) -> None:
        # El agente puede agendar eventos de día completo (cumpleaños / feriados):
        # ``all_day=true`` se propaga al ``EventCreate`` que recibe el store.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Cumpleaños",
                "start_at": _VALID_START,
                "duration_min": 1440,
                "all_day": True,
            }
        )

        assert "error" not in result
        payload = store.create_calls[0]
        assert payload.all_day is True

    async def test_all_day_defaults_false(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"title": "Normal", "start_at": _VALID_START, "duration_min": 30}
        )

        assert "error" not in result
        assert store.create_calls[0].all_day is False

    async def test_mode_string_is_accepted(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Con modo",
                "start_at": _VALID_START,
                "duration_min": 30,
                "mode": "productividad",
            }
        )

        assert "error" not in result
        assert store.create_calls[0].mode == Mode.PRODUCTIVIDAD

    async def test_missing_title_returns_invalid_arguments(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"start_at": _VALID_START, "duration_min": 30})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_empty_title_returns_invalid_arguments(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "", "start_at": _VALID_START, "duration_min": 30})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_non_positive_duration_returns_invalid_arguments(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "start_at": _VALID_START, "duration_min": 0})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_numeric_epoch_start_at_rejected(self) -> None:
        # IsoDatetime rechaza epoch numérico (mismo endurecimiento que los stubs, #38).
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "start_at": 1716000000, "duration_min": 30})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_numeric_string_epoch_rejected(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "start_at": "1716000000", "duration_min": 30})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_user_id_arg_rejected(self) -> None:
        # user_id NO puede viajar como argumento (extra='forbid'): el store ya está
        # ligado al user_id; pasarlo permitiría agendar para otro usuario.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "x",
                "start_at": _VALID_START,
                "duration_min": 30,
                "user_id": "00000000-0000-0000-0000-000000000000",
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_recurrence_without_time_zone_invalid(self) -> None:
        # Invariante ADR-018: recurrence no vacía exige time_zone (misma regla que EventCreate).
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Recurrente",
                "start_at": _VALID_START,
                "duration_min": 30,
                "recurrence": ["RRULE:FREQ=WEEKLY"],
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_recurrence_with_time_zone_ok(self) -> None:
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "Recurrente",
                "start_at": _VALID_START,
                "duration_min": 30,
                "recurrence": ["RRULE:FREQ=WEEKLY"],
                "time_zone": "America/Argentina/Buenos_Aires",
            }
        )

        assert "error" not in result
        assert store.create_calls[0].recurrence == ["RRULE:FREQ=WEEKLY"]

    async def test_title_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: title ≤ 200. Un título de 50KB no debe llegar al store.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"title": "x" * 201, "start_at": _VALID_START, "duration_min": 30}
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_location_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: location ≤ 500.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "x",
                "start_at": _VALID_START,
                "duration_min": 30,
                "location": "y" * 501,
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_time_zone_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: time_zone ≤ 64.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "x",
                "start_at": _VALID_START,
                "duration_min": 30,
                "time_zone": "z" * 65,
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_duration_over_max_rejected(self) -> None:
        # Cota LLM-fed: duration_min ≤ 43200 (un mes en minutos). Evita una duración absurda.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "start_at": _VALID_START, "duration_min": 43201})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_duration_at_max_ok(self) -> None:
        # El borde superior (43200) sigue siendo válido.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"title": "x", "start_at": _VALID_START, "duration_min": 43200})

        assert "error" not in result
        assert store.create_calls[0].duration_min == 43200

    async def test_recurrence_over_max_items_rejected(self) -> None:
        # Cota LLM-fed: recurrence ≤ 50 ítems. Una lista gigante no debe llegar a la DB.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "x",
                "start_at": _VALID_START,
                "duration_min": 30,
                "recurrence": ["RRULE:FREQ=DAILY"] * 51,
                "time_zone": "America/Argentina/Buenos_Aires",
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_recurrence_item_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: cada ítem de recurrence ≤ 500 chars.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {
                "title": "x",
                "start_at": _VALID_START,
                "duration_min": 30,
                "recurrence": ["R" * 501],
                "time_zone": "America/Argentina/Buenos_Aires",
            }
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_error_message_does_not_leak_user_value(self) -> None:
        # regla #4: el mensaje no vuelca el valor recibido del usuario.
        store = FakeCalendarStore()
        tool = AgentCreateEventTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"title": "x", "start_at": "secreto-del-usuario", "duration_min": 30}
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert "secreto-del-usuario" not in result["error"]["message"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# calendar.list_events (real)
# ---------------------------------------------------------------------------


class TestAgentListEvents:
    async def test_valid_args_calls_store_and_returns_events(self) -> None:
        store = FakeCalendarStore(list_result=[{"id": "ev-1"}, {"id": "ev-2"}])
        tool = AgentListEventsTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _VALID_START, "to_dt": _VALID_END})

        assert "error" not in result
        assert result == {"events": [{"id": "ev-1"}, {"id": "ev-2"}]}
        assert len(store.list_calls) == 1

    async def test_missing_to_dt_returns_invalid_arguments(self) -> None:
        store = FakeCalendarStore()
        tool = AgentListEventsTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _VALID_START})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_arg_rejected(self) -> None:
        store = FakeCalendarStore()
        tool = AgentListEventsTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _VALID_START, "to_dt": _VALID_END, "user_id": "x"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_from_dt_after_to_dt_rejected(self) -> None:
        # Ventana invertida: from_dt > to_dt -> invalid_arguments, no llega al store.
        store = FakeCalendarStore()
        tool = AgentListEventsTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _VALID_END, "to_dt": _VALID_START})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.list_calls

    async def test_from_dt_equals_to_dt_rejected(self) -> None:
        # Ventana de ancho cero: from_dt == to_dt -> invalid_arguments.
        store = FakeCalendarStore()
        tool = AgentListEventsTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _VALID_START, "to_dt": _VALID_START})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.list_calls


# ---------------------------------------------------------------------------
# calendar_registry
# ---------------------------------------------------------------------------


class TestCalendarRegistry:
    def test_registry_has_two_calendar_tools(self) -> None:
        store = FakeCalendarStore()
        registry = calendar_registry(store)  # type: ignore[arg-type]

        specs = registry.specs_for(["calendar"])
        names = {s.name for s in specs}

        assert names == {"calendar.create_event", "calendar.list_events"}

    def test_registry_no_specs_without_calendar_namespace(self) -> None:
        store = FakeCalendarStore()
        registry = calendar_registry(store)  # type: ignore[arg-type]

        assert registry.specs_for(["reminder"]) == []

    def test_all_specs_have_object_schema_without_docstring(self) -> None:
        store = FakeCalendarStore()
        registry = calendar_registry(store)  # type: ignore[arg-type]

        for spec in registry.specs_for(["calendar"]):
            assert spec.parameters["type"] == "object"
            assert "properties" in spec.parameters
            # El docstring del modelo Pydantic NO se filtra como description top-level.
            assert "description" not in spec.parameters

    async def test_registry_execute_create_via_registry(self) -> None:
        store = FakeCalendarStore(create_result={"id": "ev-via-reg"})
        registry = calendar_registry(store)  # type: ignore[arg-type]

        result = await registry.execute(
            "calendar.create_event",
            {"title": "x", "start_at": _VALID_START, "duration_min": 30},
        )

        assert "error" not in result
        assert result == {"id": "ev-via-reg"}

    def test_tool_names_are_snake_case_namespace_action(self) -> None:
        store = FakeCalendarStore()
        registry = calendar_registry(store)  # type: ignore[arg-type]
        for spec in registry.specs_for(["calendar"]):
            assert re.match(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", spec.name), spec.name


# ---------------------------------------------------------------------------
# Invariante de no-efecto (ADR-019): los STUBS del default siguen not_wired
# ---------------------------------------------------------------------------


class TestStubsStillNotWired:
    """La Fase E NO debe romper la invariante de no-efecto del playground observado.

    ``CreateEventTool`` / ``ListEventsTool`` (los del ``default_registry()``) deben
    seguir devolviendo ``not_wired`` (stubs sin efecto), independientes de las tools
    reales. Si esto se rompe, el playground observado (ADR-019 D2) tendría efecto.
    """

    async def test_stub_create_event_still_not_wired(self) -> None:
        result = await CreateEventTool().execute(
            {"title": "x", "start": _VALID_START, "end": _VALID_END}
        )
        assert result["status"] == "not_wired"

    async def test_stub_list_events_still_not_wired(self) -> None:
        result = await ListEventsTool().execute({"from_dt": _VALID_START, "to_dt": _VALID_END})
        assert result["status"] == "not_wired"
