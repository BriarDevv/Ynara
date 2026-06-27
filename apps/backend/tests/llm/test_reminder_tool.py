"""Tests unitarios de las reminder tools (stubs + REALES, PR-C).

Sin DB ni red — puramente unitarios. Usan un ``FakeReminderStore`` que implementa la
misma interfaz que ``ReminderStore`` sin tocar Postgres (mismo patrón que
``FakeTaskStore`` en ``test_task_tool.py``).

Verifican:
- ``reminder.set`` REAL con args válidos llama al store con un ``ReminderCreate`` bien
  armado (``when`` → ``remind_at``) y devuelve el dict del store.
- Args inválidos (falta text, vacío, > 200, epoch numérico, extra ``user_id``) ->
  ``invalid_arguments``, NUNCA propaga excepción.
- ``reminder.list`` REAL devuelve ``{reminders}``; ``from_dt >= to_dt`` → rechazado.
- ``reminder_registry()`` arma un registry con las 2 tools en namespace ``reminder``.
- Los stubs ``SetReminderTool`` / ``ListRemindersTool`` (playground observado) SIGUEN
  siendo ``not_wired`` (no se rompió la invariante de no-efecto de ADR-019).
"""

from __future__ import annotations

from datetime import datetime

from app.llm.tools.reminder import (
    AgentListRemindersTool,
    AgentSetReminderTool,
    ListRemindersTool,
    SetReminderTool,
    reminder_registry,
)
from app.schemas.reminder import ReminderCreate

_VALID_WHEN = "2026-06-22T15:00:00-03:00"
_FROM = "2026-06-22T00:00:00-03:00"
_TO = "2026-06-23T00:00:00-03:00"


class FakeReminderStore:
    """Stub de ``ReminderStore`` sin DB."""

    def __init__(
        self,
        *,
        create_result: dict[str, object] | None = None,
        list_result: list[dict[str, object]] | None = None,
    ) -> None:
        self._create_result = create_result or {"id": "rem-fake", "text": "stub"}
        self._list_result = list_result or []
        self.create_calls: list[ReminderCreate] = []
        self.window_calls: list[dict[str, object]] = []
        self.all_calls: list[dict[str, object]] = []

    async def create_reminder(self, payload: ReminderCreate) -> dict[str, object]:
        self.create_calls.append(payload)
        return self._create_result

    async def list_window(
        self, from_dt: datetime, to_dt: datetime, *, limit: int | None = None
    ) -> list[dict[str, object]]:
        self.window_calls.append({"from_dt": from_dt, "to_dt": to_dt, "limit": limit})
        return self._list_result

    async def list_all(self, *, limit: int, offset: int) -> list[dict[str, object]]:
        self.all_calls.append({"limit": limit, "offset": offset})
        return self._list_result


# ---------------------------------------------------------------------------
# reminder.set (real)
# ---------------------------------------------------------------------------


class TestAgentSetReminder:
    async def test_valid_args_calls_store_with_reminder_create(self) -> None:
        store = FakeReminderStore(create_result={"id": "r-1", "text": "Dentista"})
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"text": "Dentista", "when": _VALID_WHEN})

        assert "error" not in result
        assert result == {"id": "r-1", "text": "Dentista"}
        assert len(store.create_calls) == 1
        payload = store.create_calls[0]
        assert isinstance(payload, ReminderCreate)
        assert payload.text == "Dentista"
        # ``when`` mapea a ``remind_at``.
        assert payload.remind_at == datetime.fromisoformat(_VALID_WHEN)

    async def test_missing_text_returns_invalid_arguments(self) -> None:
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"when": _VALID_WHEN})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_empty_text_returns_invalid_arguments(self) -> None:
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"text": "", "when": _VALID_WHEN})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_text_over_max_length_rejected(self) -> None:
        # Cota LLM-fed: text ≤ 200.
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"text": "x" * 201, "when": _VALID_WHEN})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_numeric_epoch_when_rejected(self) -> None:
        # IsoDatetime rechaza epoch numérico (mismo endurecimiento que calendar/task).
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"text": "x", "when": 1716000000})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]

    async def test_extra_user_id_arg_rejected(self) -> None:
        # user_id NO puede viajar como argumento (extra='forbid').
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute(
            {"text": "x", "when": _VALID_WHEN, "user_id": "00000000-0000-0000-0000-000000000000"}
        )

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.create_calls

    async def test_error_message_does_not_leak_user_value(self) -> None:
        # regla #4: el mensaje no vuelca el valor recibido del usuario.
        store = FakeReminderStore()
        tool = AgentSetReminderTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"text": "x", "when": "secreto-del-usuario"})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert "secreto-del-usuario" not in result["error"]["message"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# reminder.list (real)
# ---------------------------------------------------------------------------


class TestAgentListReminders:
    async def test_no_args_lists_all(self) -> None:
        # Sin ventana → lista TODOS vía list_all (no list_window), con el cap del agente.
        store = FakeReminderStore(list_result=[{"id": "r-1"}, {"id": "r-2"}])
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({})

        assert "error" not in result
        assert result == {"reminders": [{"id": "r-1"}, {"id": "r-2"}]}
        assert len(store.all_calls) == 1
        assert not store.window_calls
        from app.llm.tools.base import AGENT_LIST_RESULT_LIMIT

        assert store.all_calls[0] == {"limit": AGENT_LIST_RESULT_LIMIT, "offset": 0}

    async def test_valid_window_calls_store_and_returns_reminders(self) -> None:
        store = FakeReminderStore(list_result=[{"id": "r-1"}, {"id": "r-2"}])
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _FROM, "to_dt": _TO})

        assert "error" not in result
        assert result == {"reminders": [{"id": "r-1"}, {"id": "r-2"}]}
        assert len(store.window_calls) == 1
        assert not store.all_calls
        from app.llm.tools.base import AGENT_LIST_RESULT_LIMIT

        assert store.window_calls[0]["limit"] == AGENT_LIST_RESULT_LIMIT

    async def test_partial_window_only_from_dt_rejected(self) -> None:
        # Solo from_dt (sin to_dt) → ventana incompleta → invalid_arguments.
        store = FakeReminderStore()
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _FROM})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.window_calls
        assert not store.all_calls

    async def test_partial_window_only_to_dt_rejected(self) -> None:
        # Solo to_dt (sin from_dt) → ventana incompleta → invalid_arguments.
        store = FakeReminderStore()
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"to_dt": _TO})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.window_calls
        assert not store.all_calls

    async def test_inverted_window_rejected(self) -> None:
        # from_dt >= to_dt → invalid_arguments (ventana sin sentido).
        store = FakeReminderStore()
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _TO, "to_dt": _FROM})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
        assert not store.window_calls

    async def test_equal_window_rejected(self) -> None:
        # from_dt == to_dt (ancho cero) también se rechaza.
        store = FakeReminderStore()
        tool = AgentListRemindersTool(store)  # type: ignore[arg-type]

        result = await tool.execute({"from_dt": _FROM, "to_dt": _FROM})

        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]


# ---------------------------------------------------------------------------
# reminder_registry
# ---------------------------------------------------------------------------


class TestReminderRegistry:
    def test_registry_has_two_reminder_tools(self) -> None:
        store = FakeReminderStore()
        registry = reminder_registry(store)  # type: ignore[arg-type]

        names = {s.name for s in registry.specs_for(["reminder"])}
        assert names == {"reminder.set", "reminder.list"}

    async def test_registry_execute_set_via_registry(self) -> None:
        store = FakeReminderStore(create_result={"id": "r-via-reg"})
        registry = reminder_registry(store)  # type: ignore[arg-type]

        result = await registry.execute("reminder.set", {"text": "x", "when": _VALID_WHEN})

        assert "error" not in result
        assert result == {"id": "r-via-reg"}


# ---------------------------------------------------------------------------
# Invariante de no-efecto (ADR-019): los STUBS del default siguen not_wired
# ---------------------------------------------------------------------------


class TestStubsStillNotWired:
    async def test_stub_set_reminder_still_not_wired(self) -> None:
        result = await SetReminderTool().execute({"text": "x", "when": _VALID_WHEN})
        assert result["status"] == "not_wired"

    async def test_stub_list_reminders_still_not_wired(self) -> None:
        result = await ListRemindersTool().execute({})
        assert result["status"] == "not_wired"

    async def test_stub_set_reminder_validates_args(self) -> None:
        # El stub también valida (epoch numérico en when rechazado).
        result = await SetReminderTool().execute({"text": "x", "when": 1716000000})
        assert result["error"]["code"] == "invalid_arguments"  # type: ignore[index]
