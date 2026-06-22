"""Tests de la pasada multi-tool del agente para el namespace ``task`` (Fase D1).

Complementan ``test_agent_pass.py`` (que cubre calendar): acá se verifica que la
generalización MULTI-TOOL del ``agent_pass`` (Opción A: registry combinado por
namespaces habilitados) acciona ``task.create_task`` en un modo que habilita ``task``
en ``tools_enabled``, y que un modo SIN tools de agente no acciona.

UNIT: FakeLlmClient guionado para emitir un tool_call ``task.create_task`` + el
  ``TaskStore`` parcheado por un fake (sin DB).
INTEGRATION (``@pytest.mark.integration``): contra la DB de tests real — el tool_call
  crea la tarea del user correcto; aislamiento por user_id; idempotencia en retry.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.clients.fakes import FakeLlmClient
from app.llm.schemas import CompletionResult, ToolCall
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate
from app.workflows.agent_pass import _async_agent_pass

# Modo real con 'task' en tools_enabled (ynara.config.json): productividad (qwen).
MODE_WITH_TASK = "productividad"
# Modo sin tools de agente accionables: vida (gemma, tools_enabled=[]).
MODE_WITHOUT_AGENT_TOOLS = "vida"

USER_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())


def _make_llm_with_create_task(*, title: str = "Comprar pan") -> FakeLlmClient:
    """FakeLlmClient guionado: 1ra completion = tool_call task.create_task; 2da = stop."""
    client = FakeLlmClient(served_models=frozenset({"qwen"}))
    tc = ToolCall(
        id="tc-1",
        name="task.create_task",
        arguments={"title": title},
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


class _FakeTaskStore:
    """Stub de ``TaskStore`` para los unit (sin DB)."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.create_calls: list[TaskCreate] = []

    async def create_task(self, payload: TaskCreate) -> dict[str, object]:
        self.create_calls.append(payload)
        return {"id": "task-fake", "title": payload.title}

    async def list_tasks(self, *_args: Any, **_kwargs: Any) -> list[dict[str, object]]:
        return []


async def _seed_user(session: AsyncSession) -> str:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return str(user.id)


async def _count_tasks(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.scalar(select(func.count()).select_from(Task).where(Task.user_id == user_id))
    ) or 0


# ===========================================================================
# UNIT — cuerpo async (sin DB: session MagicMock + store parcheado)
# ===========================================================================


class TestAsyncAgentPassTaskUnit:
    async def test_task_mode_executes_tool_call(self) -> None:
        """Un modo con task + tool_call -> ejecuta create_task vía el store fake."""
        client = _make_llm_with_create_task(title="Comprar pan")
        session = MagicMock(spec=AsyncSession)
        fake_store = _FakeTaskStore()

        with patch("app.tasks.store.TaskStore", return_value=fake_store):
            result = await _async_agent_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="acordate de comprar pan",
                model_response="dale, lo anoto",
                mode=MODE_WITH_TASK,
                llm_client=client,
                session=session,
            )

        assert result == 1
        assert len(fake_store.create_calls) == 1
        assert fake_store.create_calls[0].title == "Comprar pan"

    async def test_mode_without_agent_tools_is_noop(self) -> None:
        """Un modo sin tools de agente (tools_enabled=[]) NO acciona."""
        client = _make_llm_with_create_task()
        session = MagicMock(spec=AsyncSession)

        result = await _async_agent_pass(
            user_id=USER_ID,
            session_id=SESSION_ID,
            user_msg="hola",
            model_response="chau",
            mode=MODE_WITHOUT_AGENT_TOOLS,
            llm_client=client,
            session=session,
        )

        assert result == 0
        # No se llamó al LLM (gate cortó antes de armar el loop).
        assert not client.complete_calls

    async def test_specs_combine_calendar_and_task(self) -> None:
        """En productividad (calendar + task) el modelo ve AMBOS namespaces de tools."""
        client = _make_llm_with_create_task()
        session = MagicMock(spec=AsyncSession)
        fake_store = _FakeTaskStore()

        with (
            patch("app.tasks.store.TaskStore", return_value=fake_store),
            patch("app.calendar.store.CalendarEventStore"),
        ):
            await _async_agent_pass(
                user_id=USER_ID,
                session_id=SESSION_ID,
                user_msg="anotá algo",
                model_response="dale",
                mode=MODE_WITH_TASK,
                llm_client=client,
                session=session,
            )

        # El primer complete() recibió las specs combinadas: calendar.* + task.*.
        first_call = client.complete_calls[0]
        tool_specs = first_call["tools"]
        names = {spec.name for spec in tool_specs}  # type: ignore[union-attr]
        assert "task.create_task" in names
        assert "task.list_tasks" in names
        assert "calendar.create_event" in names


# ===========================================================================
# INTEGRATION — DB real
# ===========================================================================


@pytest.mark.integration
async def test_integration_create_task_for_correct_user(db_session: AsyncSession) -> None:
    """tool_call task.create_task -> crea la tarea en la DB para el user correcto."""
    user_id = await _seed_user(db_session)
    client = _make_llm_with_create_task(title="Pagar la luz")

    result = await _async_agent_pass(
        user_id=user_id,
        session_id=SESSION_ID,
        user_msg="recordame pagar la luz",
        model_response="listo, lo anoto",
        mode=MODE_WITH_TASK,
        llm_client=client,
        session=db_session,
    )

    assert result == 1
    rows = list(
        (await db_session.execute(select(Task).where(Task.user_id == UUID(user_id))))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Pagar la luz"


@pytest.mark.integration
async def test_integration_mode_without_agent_tools_creates_nothing(
    db_session: AsyncSession,
) -> None:
    """Un modo sin tools de agente -> NO crea tarea (gate config-driven)."""
    user_id = await _seed_user(db_session)
    client = _make_llm_with_create_task()

    result = await _async_agent_pass(
        user_id=user_id,
        session_id=SESSION_ID,
        user_msg="anotá algo",
        model_response="dale",
        mode=MODE_WITHOUT_AGENT_TOOLS,
        llm_client=client,
        session=db_session,
    )

    assert result == 0
    assert await _count_tasks(db_session, UUID(user_id)) == 0


@pytest.mark.integration
async def test_integration_idempotent_on_retry(db_session: AsyncSession) -> None:
    """Re-correr la pasada con el mismo turno NO duplica la tarea (idempotencia)."""
    user_id = await _seed_user(db_session)

    for _ in range(2):
        client = _make_llm_with_create_task(title="Comprar pan")
        await _async_agent_pass(
            user_id=user_id,
            session_id=SESSION_ID,
            user_msg="comprá pan",
            model_response="dale",
            mode=MODE_WITH_TASK,
            llm_client=client,
            session=db_session,
        )

    assert await _count_tasks(db_session, UUID(user_id)) == 1


# ===========================================================================
# Hogar canónico de ``_AGENT_TOOL_BUILDERS`` (ADR-022): re-export desde agent_pass
# ===========================================================================


def test_agent_tool_builders_reexported_from_agent_pass() -> None:
    """``_AGENT_TOOL_BUILDERS`` se re-exporta desde ``agent_pass`` y es el MISMO objeto
    que el del hogar canónico (``app.llm.tools.agent_registry``).

    ADR-022 movió el mapping a la capa ``llm.tools`` (para que el chat de producción lo
    reuse sin importar workflows). ``agent_pass`` lo re-importa para que la pasada async
    (dormant) lo siga usando con el mismo comportamiento. Este test LOCKEA que el
    re-export apunta al canónico (no a una copia divergente).
    """
    from app.llm.tools.agent_registry import _AGENT_TOOL_BUILDERS as canonical
    from app.workflows.agent_pass import _AGENT_TOOL_BUILDERS as reexported

    assert reexported is canonical
    assert set(canonical.keys()) == {"calendar", "task"}
