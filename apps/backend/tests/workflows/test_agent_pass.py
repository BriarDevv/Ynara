"""Tests de la pasada async del agente ``agent_turn_pass`` (Fase E, ADR-021).

UNIT: validan el wrapper Celery + el cuerpo async sin DB ni red (FakeLlmClient
  guionado para emitir tool_calls + ``CalendarEventStore`` parcheado por un fake).
INTEGRATION (``@pytest.mark.integration``): validan ``_async_agent_pass`` contra la
  DB de tests real — un tool_call ``calendar.create_event`` crea el evento del user
  correcto; un modo SIN calendar en tools_enabled NO crea evento; aislamiento por
  user_id.

Reglas aplicadas (espejo de ``test_consolidation.py``):
- Ningún dato de usuario en logs (regla #4): el contenido del turno va en variables.
- El wrapper ``agent_turn_pass`` NUNCA propaga excepciones.
- Gate config-driven: solo modos con 'calendar' en tools_enabled accionan.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.fakes import FakeLlmClient
from app.llm.schemas import CompletionResult, ToolCall
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.schemas.calendar_event import EventCreate
from app.workflows.agent_pass import _async_agent_pass, agent_turn_pass

# Modo real con 'calendar' en tools_enabled (ynara.config.json): productividad (qwen).
MODE_WITH_CALENDAR = "productividad"
# Modo sin calendar en tools_enabled: vida (gemma, tools_enabled=[]).
MODE_WITHOUT_CALENDAR = "vida"

USER_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())

_VALID_START = "2026-06-22T15:00:00-03:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_with_create_event(
    *,
    title: str = "Reunión",
    start_at: str = _VALID_START,
    duration_min: int = 30,
) -> FakeLlmClient:
    """FakeLlmClient guionado: 1ra completion = tool_call calendar.create_event; 2da = stop.

    Reproduce el flujo del tool loop: el modelo pide la tool, el loop la ejecuta, y
    el modelo cierra con un ``stop`` (sin más tool_calls).
    """
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    tc = ToolCall(
        id="tc-1",
        name="calendar.create_event",
        arguments={"title": title, "start_at": start_at, "duration_min": duration_min},
    )
    client.queue_result(
        CompletionResult(
            text="",
            tool_calls=[tc],
            finish_reason="tool_calls",
            prompt_tokens=10,
            completion_tokens=5,
            model_name="qwen",
            latency_ms=5.0,
        )
    )
    client.queue_result(
        CompletionResult(
            text="listo",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            model_name="qwen",
            latency_ms=5.0,
        )
    )
    return client


class _FakeCalendarStore:
    """Stub de ``CalendarEventStore`` para los unit (sin DB)."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.create_calls: list[EventCreate] = []

    async def create_event(self, payload: EventCreate) -> dict[str, object]:
        self.create_calls.append(payload)
        return {"id": "ev-fake", "title": payload.title}

    async def list_events(self, *_args: Any, **_kwargs: Any) -> list[dict[str, object]]:
        return []


async def _seed_user(session: AsyncSession) -> str:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return str(user.id)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


async def _count_events(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id == user_id)
        )
    ) or 0


# ===========================================================================
# UNIT — wrapper Celery
# ===========================================================================


class TestAgentTurnPassWrapper:
    """Tests del wrapper Celery ``agent_turn_pass`` (sin DB ni red)."""

    def test_calls_async_with_correct_args(self) -> None:
        with patch(
            "app.workflows.agent_pass._async_agent_pass", new_callable=AsyncMock
        ) as mock_async:
            mock_async.return_value = 1
            agent_turn_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="agendá dentista mañana 10am",
                model_response="dale, lo anoto",
                mode=MODE_WITH_CALENDAR,
            )
            mock_async.assert_called_once_with(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="agendá dentista mañana 10am",
                model_response="dale, lo anoto",
                mode=MODE_WITH_CALENDAR,
            )

    def test_wrapper_never_propagates_exception(self) -> None:
        """Un fallo del cuerpo async NO debe propagar (el worker no muere)."""
        with patch(
            "app.workflows.agent_pass._async_agent_pass", new_callable=AsyncMock
        ) as mock_async:
            mock_async.side_effect = RuntimeError("boom con dato sensible")
            # No debe levantar.
            agent_turn_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="x",
                model_response="y",
                mode=MODE_WITH_CALENDAR,
            )

    def test_task_name(self) -> None:
        assert agent_turn_pass.name == "workflows.agent_turn_pass"


# ===========================================================================
# UNIT — cuerpo async (sin DB: session MagicMock + store parcheado)
# ===========================================================================


class TestAsyncAgentPassUnit:
    async def test_mode_without_calendar_is_noop(self) -> None:
        """Un modo SIN 'calendar' en tools_enabled NO acciona (gate config-driven)."""
        client = _make_llm_with_create_event()
        session = MagicMock(spec=AsyncSession)

        result = await _async_agent_pass(
            user_id=USER_ID,
            session_id=SESSION_ID,
            user_msg="hola",
            model_response="chau",
            mode=MODE_WITHOUT_CALENDAR,
            llm_client=client,
            session=session,
        )

        assert result == 0
        # No se llamó al LLM (gate cortó antes de armar el loop).
        assert not client.complete_calls

    async def test_unknown_mode_is_noop(self) -> None:
        """Un modo desconocido (payload corrupto) -> no-op sin crash."""
        client = _make_llm_with_create_event()
        session = MagicMock(spec=AsyncSession)

        result = await _async_agent_pass(
            user_id=USER_ID,
            session_id=SESSION_ID,
            user_msg="x",
            model_response="y",
            mode="modo-inexistente",
            llm_client=client,
            session=session,
        )

        assert result == 0

    async def test_calendar_mode_executes_tool_call(self) -> None:
        """Un modo con calendar + tool_call -> ejecuta create_event vía el store real-fake."""
        client = _make_llm_with_create_event(title="Dentista")
        session = MagicMock(spec=AsyncSession)
        fake_store = _FakeCalendarStore()

        with patch("app.services.calendar.CalendarEventStore", return_value=fake_store):
            result = await _async_agent_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="agendá dentista",
                model_response="dale",
                mode=MODE_WITH_CALENDAR,
                llm_client=client,
                session=session,
            )

        # Una acción ejecutada (el create_event).
        assert result == 1
        assert len(fake_store.create_calls) == 1
        assert fake_store.create_calls[0].title == "Dentista"

    async def test_system_prompt_includes_datetime_preamble(self) -> None:
        """El system de la pasada antepone el preámbulo de fecha/hora actual (gap E2E).

        Sin esto el agente no podía resolver "mañana"/"el lunes" y pedía la fecha en
        vez de agendar. Se parchea ``current_now`` a una fecha fija y se inspecciona el
        ``system`` que el FakeLlmClient recibió en ``complete_calls``.
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        client = _make_llm_with_create_event(title="Gym")
        session = MagicMock(spec=AsyncSession)
        fake_store = _FakeCalendarStore()
        fixed = datetime(2026, 7, 22, 18, 30, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))

        with (
            patch("app.services.calendar.CalendarEventStore", return_value=fake_store),
            patch("app.workflows.agent_pass.current_now", return_value=fixed),
        ):
            await _async_agent_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="agendame gym mañana 18hs",
                model_response="dale, lo anoto",
                mode=MODE_WITH_CALENDAR,
                llm_client=client,
                session=session,
            )

        # El primer complete recibió el system con el preámbulo de fecha al inicio.
        system_msg = client.complete_calls[0]["messages"][0]
        assert system_msg.role == "system"
        assert system_msg.content.startswith("Fecha y hora actual: ")
        # 2026-07-22 cae miércoles (el día se deriva con weekday(), no se hardcodea).
        assert "miércoles 22 de julio de 2026, 18:30 (hora de Argentina)" in system_msg.content
        assert "resolver fechas relativas" in system_msg.content
        # El cuerpo estático sigue presente (no se perdió al anteponer el preámbulo).
        assert "ACCIONAR" in system_msg.content

    async def test_no_tool_call_means_zero_actions(self) -> None:
        """Si el modelo no llama ninguna tool (nada para agendar), 0 acciones."""
        client = FakeLlmClient(served_models=frozenset({"qwen"}))
        client.queue_result(
            CompletionResult(
                text="nada para agendar",
                finish_reason="stop",
                prompt_tokens=5,
                completion_tokens=5,
                model_name="qwen",
                latency_ms=1.0,
            )
        )
        session = MagicMock(spec=AsyncSession)
        fake_store = _FakeCalendarStore()

        with patch("app.services.calendar.CalendarEventStore", return_value=fake_store):
            result = await _async_agent_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="hola, qué tal",
                model_response="todo bien",
                mode=MODE_WITH_CALENDAR,
                llm_client=client,
                session=session,
            )

        assert result == 0
        assert not fake_store.create_calls


# ===========================================================================
# INTEGRATION — DB real
# ===========================================================================


@pytest.mark.integration
async def test_integration_create_event_for_correct_user(db_session: AsyncSession) -> None:
    """tool_call calendar.create_event -> crea el evento en la DB para el user correcto."""
    user_id = await _seed_user(db_session)
    client = _make_llm_with_create_event(title="Reunión equipo", duration_min=45)

    result = await _async_agent_pass(
        user_id=user_id,
        session_id=SESSION_ID,
        user_msg="agendá reunión de equipo mañana 3pm",
        model_response="listo, la anoto",
        mode=MODE_WITH_CALENDAR,
        llm_client=client,
        session=db_session,
    )

    assert result == 1

    # El evento quedó en la DB para el user correcto.
    rows = list(
        (
            await db_session.execute(
                select(CalendarEvent).where(CalendarEvent.user_id == UUID(user_id))
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Reunión equipo"
    assert rows[0].duration_min == 45


@pytest.mark.integration
async def test_integration_mode_without_calendar_creates_nothing(
    db_session: AsyncSession,
) -> None:
    """Un modo SIN calendar en tools_enabled -> NO crea evento (gate config-driven)."""
    user_id = await _seed_user(db_session)
    client = _make_llm_with_create_event()

    result = await _async_agent_pass(
        user_id=user_id,
        session_id=SESSION_ID,
        user_msg="agendá algo",
        model_response="dale",
        mode=MODE_WITHOUT_CALENDAR,
        llm_client=client,
        session=db_session,
    )

    assert result == 0
    assert await _count_events(db_session, UUID(user_id)) == 0


@pytest.mark.integration
async def test_integration_isolation_by_user(db_session: AsyncSession) -> None:
    """El evento se crea para el user de la pasada, no para otro (aislamiento)."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    client = _make_llm_with_create_event(title="De A")

    await _async_agent_pass(
        user_id=user_a,
        session_id=SESSION_ID,
        user_msg="agendá",
        model_response="dale",
        mode=MODE_WITH_CALENDAR,
        llm_client=client,
        session=db_session,
    )

    assert await _count_events(db_session, UUID(user_a)) == 1
    assert await _count_events(db_session, UUID(user_b)) == 0


@pytest.mark.integration
async def test_integration_idempotent_on_retry(db_session: AsyncSession) -> None:
    """Re-correr la pasada con el mismo turno NO duplica el evento (idempotencia)."""
    user_id = await _seed_user(db_session)

    # Dos pasadas idénticas (simula un reintento de Celery del mismo turno).
    for _ in range(2):
        client = _make_llm_with_create_event(title="Dentista", duration_min=60)
        await _async_agent_pass(
            user_id=user_id,
            session_id=SESSION_ID,
            user_msg="agendá dentista",
            model_response="dale",
            mode=MODE_WITH_CALENDAR,
            llm_client=client,
            session=db_session,
        )

    # Una sola fila pese a las dos pasadas (dedupe por tupla natural en el store).
    assert await _count_events(db_session, UUID(user_id)) == 1
