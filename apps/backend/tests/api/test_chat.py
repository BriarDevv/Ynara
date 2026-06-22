"""Tests E2E del endpoint ``POST /v1/chat`` (M9 Ola 2).

Todos son ``integration`` (tocan la DB de tests dedicada: el endpoint hace
``session.commit()``). Ejercitan el stack completo HTTP -> deps -> router con
clientes Fake, sin red ni Redis:

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, asi
  los asserts consultan la MISMA sesion que commitea el endpoint.
- ``get_llm_client`` / ``get_embedder`` / ``get_reranker`` se overridean con
  Fakes; el ``FakeLlmClient`` se programa con ``CompletionResult`` para que
  ``route()`` responda determinista.
- ``app.services.chat.consolidate_turn`` se parchea (Qwen encola post-commit; no
  hay Redis). El enqueue vive en ``ChatService`` (movido de ``route()`` en M10 Ola 0).

Limpieza: el endpoint commitea, asi que el rollback del fixture NO alcanza para
los datos persistidos. Cada test borra el ``User`` que sembro al final
(``ON DELETE CASCADE`` arrastra sus ``ChatSession``), dejando la DB de tests
idempotente.

Cubre el mapeo de errores (decision #7 M9): 200 happy path (Gemma/Qwen), reuso
de sesion, 401 (sin/invalid token), 422 (validacion), 404 (sesion ajena), 409
(mode mismatch).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_embedder, get_llm_client, get_reranker, get_token_store
from app.core.security import create_access_token
from app.core.token_store import InMemoryTokenStore, RedisTokenStore, TokenStore
from app.enums import Mode, TurnRole
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult, ToolCall
from app.main import app
from app.memory.conversation_turns import ConversationTurnStore
from app.models.conversation_turn import ConversationTurn
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completion(
    *,
    text: str = "hola",
    finish_reason: str = "stop",
    tool_calls: list[ToolCall] | None = None,
    model_name: str = "gemma4",
) -> CompletionResult:
    """``CompletionResult`` minimo para programar el ``FakeLlmClient``."""
    return CompletionResult(
        text=text,
        finish_reason=finish_reason,
        tool_calls=tool_calls or [],
        prompt_tokens=10,
        completion_tokens=5,
        model_name=model_name,
        latency_ms=42.0,
    )


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User minimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Borra el User sembrado (CASCADE arrastra sus ChatSession). Idempotente."""
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
    await session.commit()


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT valido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(
    db_session: AsyncSession,
    *,
    llm_client: FakeLlmClient,
    store: TokenStore | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Context-ish helper: overridea las deps y devuelve un AsyncClient ASGI.

    El caller debe usar el cliente dentro de ``async with`` y limpiar los
    overrides despues (lo hace cada test en su ``finally`` via
    ``app.dependency_overrides.clear()``).

    ``store`` (S4): el ``TokenStore`` del rate-limit. Por default NO se overridea
    ``get_token_store`` (usa el ``InMemoryTokenStore`` sin freno del conftest); los
    tests de rate-limit pasan el suyo para forzar un threshold chico o un store que
    degrada (fail-open).
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: llm_client
    app.dependency_overrides[get_embedder] = FakeEmbeddingClient
    app.dependency_overrides[get_reranker] = FakeReranker
    if store is not None:
        app.dependency_overrides[get_token_store] = lambda: store
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _chat_ratelimit_settings(*, chat_max: int) -> Settings:
    """Settings determinista para los tests de rate-limit del chat (threshold chico)."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod-min-32b",
        CHAT_MAX_REQUESTS=chat_max,
        CHAT_WINDOW_SECONDS=60,
    )


class _BoomRedisClient:
    """Cliente Redis que lanza en toda op: ejercita el fail-open del store."""

    async def eval(self, *a: object, **k: object) -> int:
        raise RuntimeError("redis down")

    async def exists(self, *a: object) -> int:
        raise RuntimeError("redis down")

    async def set(self, *a: object, **k: object) -> None:
        raise RuntimeError("redis down")

    async def mget(self, *a: object) -> list[None]:
        raise RuntimeError("redis down")

    async def delete(self, *a: object) -> None:
        raise RuntimeError("redis down")


# ---------------------------------------------------------------------------
# Happy path: Gemma (vida) — conversacional, sin tools, no encola consolidacion
# ---------------------------------------------------------------------------


async def test_happy_path_gemma_vida_creates_session(db_session: AsyncSession) -> None:
    """200 + body ChatHttpResponse; se crea una ChatSession persistida."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola, todo bien?", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "hola, todo bien?"
        assert body["actions"] == []
        assert body["finish_reason"] == "stop"
        # session_id es un UUID serializado.
        returned_id = uuid.UUID(body["session_id"])

        # Se persistio una ChatSession para ese user/mode (mismo id devuelto).
        cs = await db_session.get(ChatSession, returned_id)
        assert cs is not None
        assert cs.user_id == user.id
        assert cs.mode == Mode.VIDA
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Happy path: Qwen (productividad) — agent, tool loop con actions
# ---------------------------------------------------------------------------


async def test_happy_path_qwen_productividad_with_actions(db_session: AsyncSession) -> None:
    """200 + actions pobladas (tool loop). Encola consolidacion (mockeada)."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    # Vuelta 1: tool_call memory.search; vuelta 2: stop con texto.
    tc = ToolCall(id="tc-1", name="memory.search", arguments={"query": "reuniones"})
    fake.queue_result(
        _completion(text="", finish_reason="tool_calls", tool_calls=[tc], model_name="qwen")
    )
    fake.queue_result(
        _completion(text="Listo, lo agende.", finish_reason="stop", model_name="qwen")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        # Patch target: el enqueue de consolidacion vive en ChatService (movido de
        # route() en M10 Ola 0), asi que el binding real es ``app.services.chat.
        # consolidate_turn``. La pasada async del agente YA NO se encola (ADR-022): las
        # tools de agente corren sincronas en route(); por eso no se parchea ningun
        # ``agent_turn_pass`` aca.
        with patch("app.services.chat.consolidate_turn") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "agenda una reunion", "mode": "productividad"},
                    headers=_bearer(user.id),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "Listo, lo agende."
        assert len(body["actions"]) == 1
        action = body["actions"][0]
        assert action["id"] == "tc-1"
        assert action["name"] == "memory.search"
        assert action["arguments"] == {"query": "reuniones"}
        # Qwen escribe memoria -> se encolo la consolidacion (post-commit).
        mock_task.delay.assert_called_once()
        # Los kwargs replican EXACTO los que pasaba route(): todos str. El
        # session_id es el de la ChatSession ya devuelta/persistida -> el enqueue
        # ocurrio DESPUES del commit (la fila existe cuando se encola).
        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs == {
            "user_id": str(user.id),
            "session_id": body["session_id"],
            "user_msg": "agenda una reunion",
            "model_response": "Listo, lo agende.",
            "mode": "productividad",
        }
        # La ChatSession ya esta persistida en la DB cuando se encolo.
        persisted = await db_session.get(ChatSession, uuid.UUID(body["session_id"]))
        assert persisted is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Fail-open: el enqueue de consolidacion (broker Redis caido) NO rompe el turno
# ---------------------------------------------------------------------------


async def test_enqueue_failure_does_not_break_turn(db_session: AsyncSession) -> None:
    """Si ``consolidate_turn.delay`` lanza (broker caido), POST /chat sigue 200.

    El turno ya esta commiteado cuando se encola; un fallo del enqueue debe
    degradar (fail-open, igual que el TokenStore), no devolver 500 con el turno
    ya persistido. Usa Qwen (``writes_memory=True``) para ejercitar el path de
    enqueue y parchea ``delay`` para que tire ``RuntimeError`` (simula
    OperationalError / ConnectionError del broker Redis).
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(
        _completion(text="Listo, lo agende.", finish_reason="stop", model_name="qwen")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        # El enqueue de consolidacion falla (broker caido): NO debe tumbar el turno
        # (fail-open). La pasada async del agente ya no se encola (ADR-022).
        with patch("app.services.chat.consolidate_turn") as mock_task:
            mock_task.delay = MagicMock(side_effect=RuntimeError("broker down"))
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "agenda una reunion", "mode": "productividad"},
                    headers=_bearer(user.id),
                )

        # 200 pese al fallo del enqueue: el turno se commiteo y la respuesta es valida.
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "Listo, lo agende."
        assert body["finish_reason"] == "stop"
        # Se intento encolar la consolidacion (y fallo): el path fail-open se ejercito.
        mock_task.delay.assert_called_once()
        # La ChatSession quedo persistida pese al fallo del enqueue (commit previo).
        persisted = await db_session.get(ChatSession, uuid.UUID(body["session_id"]))
        assert persisted is not None
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Tools SÍNCRONAS en el chat de produccion (ADR-022): calendar.create_event REAL
# ---------------------------------------------------------------------------


async def test_chat_executes_calendar_tool_synchronously_and_persists(
    db_session: AsyncSession,
) -> None:
    """En productividad, una tool_call calendar.create_event se EJECUTA en el turno (ADR-022).

    Reemplaza el contrato viejo (encolar ``agent_turn_pass`` async): ahora el tool-loop
    de produccion corre con el registry REAL (``build_chat_tool_registry``), asi que:
      (a) la respuesta ``actions`` incluye calendar.create_event con un ``result`` real
          (``id`` presente, NO ``not_wired``), y
      (b) queda una fila en ``calendar_events`` para el user despues del turno (el
          commit del turno persiste la escritura de la tool, atomico).
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    # Vuelta 1: tool_call calendar.create_event (args validos); vuelta 2: stop + confirma.
    tc = ToolCall(
        id="tc-cal-1",
        name="calendar.create_event",
        arguments={
            "title": "Dentista",
            "start_at": "2026-06-23T10:00:00-03:00",
            "duration_min": 30,
        },
    )
    fake.queue_result(
        _completion(text="", finish_reason="tool_calls", tool_calls=[tc], model_name="qwen")
    )
    fake.queue_result(
        _completion(text="Listo, te agendé el dentista.", finish_reason="stop", model_name="qwen")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        # Solo se parchea la consolidacion (memoria, sigue async). La pasada del agente ya
        # no se encola (ADR-022): no hay nada que mockear ahi.
        with patch("app.services.chat.consolidate_turn") as mock_cons:
            mock_cons.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "agenda dentista mañana 10am", "mode": "productividad"},
                    headers=_bearer(user.id),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "Listo, te agendé el dentista."

        # (a) La accion calendar.create_event tiene un result REAL (id presente, no stub).
        cal_actions = [a for a in body["actions"] if a["name"] == "calendar.create_event"]
        assert len(cal_actions) == 1
        result = cal_actions[0]["result"]
        assert "id" in result
        assert result.get("title") == "Dentista"
        # El stub devolveria {"status": "not_wired", ...}: confirmamos que NO es el stub.
        assert result.get("status") != "not_wired"

        # (b) Existe la fila real en calendar_events para el user (commiteada con el turno).
        from app.models.calendar_event import CalendarEvent

        rows = list(
            (
                await db_session.execute(
                    select(CalendarEvent).where(CalendarEvent.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].title == "Dentista"
        assert rows[0].duration_min == 30
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_chat_degraded_after_tool_flush_rolls_back_event(
    db_session: AsyncSession,
) -> None:
    """Si una tool flushea un evento y DESPUÉS el LLM degrada, el evento se ROLLBACKea (ADR-022).

    El SAVEPOINT de ``ChatService.run_turn`` acota las escrituras de tools: un turno que
    termina ``degraded`` (porque ``route()`` capturó un ``LlmError`` en una iteración
    posterior del tool-loop) NO debe dejar el evento fantasma sin un turno que lo confirme.
      - vuelta 1: tool_call calendar.create_event (flushea el evento), luego
      - vuelta 2: el LLM tira un ``LlmError`` -> ``route()`` degrada -> savepoint rollback.
    Resultado esperado: 0 filas en ``calendar_events`` y finish_reason 'degraded'.
    """
    from app.llm.errors import LlmUnavailableError

    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    tc = ToolCall(
        id="tc-cal-deg",
        name="calendar.create_event",
        arguments={
            "title": "Dentista",
            "start_at": "2026-06-23T10:00:00-03:00",
            "duration_min": 30,
        },
    )
    fake.queue_result(
        _completion(text="", finish_reason="tool_calls", tool_calls=[tc], model_name="qwen")
    )
    # Vuelta 2: el LLM falla -> route() captura el LlmError y devuelve finish_reason='degraded'.
    fake.queue_error(LlmUnavailableError("backend caido"))

    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.services.chat.consolidate_turn") as mock_cons:
            mock_cons.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "agenda dentista mañana 10am", "mode": "productividad"},
                    headers=_bearer(user.id),
                )

        assert resp.status_code == 200
        assert resp.json()["finish_reason"] == "degraded"

        # El evento flusheado por la tool se ROLLBACKeó con el savepoint: 0 filas.
        from app.models.calendar_event import CalendarEvent

        rows = list(
            (
                await db_session.execute(
                    select(CalendarEvent).where(CalendarEvent.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert rows == []
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_chat_non_calendar_mode_creates_no_events(db_session: AsyncSession) -> None:
    """Un modo SIN 'calendar' en tools_enabled (vida, gemma) NO crea eventos (gating ADR-022).

    El registry del chat para vida (``tools_enabled=[]``) queda vacio, asi que ni
    siquiera se expone calendar al modelo: no hay efecto.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(
        _completion(text="todo bien por aca.", finish_reason="stop", model_name="gemma4")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola, como va", "mode": "vida"},
                headers=_bearer(user.id),
            )

        assert resp.status_code == 200

        from app.models.calendar_event import CalendarEvent

        count = (
            await db_session.execute(
                select(func.count())
                .select_from(CalendarEvent)
                .where(CalendarEvent.user_id == user.id)
            )
        ).scalar_one()
        assert count == 0
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Persistencia de turnos: un /chat OK deja 2 turnos (user seq=0 / model seq=1)
# ---------------------------------------------------------------------------


async def test_chat_ok_persists_two_turns_user_and_model(db_session: AsyncSession) -> None:
    """Tras un POST /chat exitoso hay 2 turnos en ConversationTurnStore: user(seq=0) +
    model(seq=1), con los roles correctos y el contenido descifrado.

    Lock del contrato de persistencia de turnos del happy path (issue #209) desde la
    superficie del endpoint /chat.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola, todo bien?", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola Ynara", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        session_id = uuid.UUID(resp.json()["session_id"])

        # Exactamente 2 turnos persistidos, con orden + roles + contenido correctos.
        store = ConversationTurnStore(db_session, user.id)
        turns = await store.list_for_session(session_id)
        assert [t.seq for t in turns] == [0, 1]
        assert [t.role for t in turns] == [TurnRole.USER, TurnRole.MODEL]
        assert turns[0].content == "hola Ynara"
        assert turns[1].content == "hola, todo bien?"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_chat_degraded_response_persists_no_turns(db_session: AsyncSession) -> None:
    """Una respuesta ``finish_reason='degraded'`` NO genera filas de turnos.

    Espejo negativo del happy path: si el turno degradó, no se persiste ningún turno
    (ni se consolida). Cuenta 0 filas en ``conversation_turns`` para esa sesión.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    fake.queue_result(
        _completion(text="respuesta degradada", finish_reason="degraded", model_name="qwen")
    )

    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.services.chat.consolidate_turn") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat",
                    json={"text": "hola", "mode": "productividad"},
                    headers=_bearer(user.id),
                )
        assert resp.status_code == 200
        assert resp.json()["finish_reason"] == "degraded"
        session_id = uuid.UUID(resp.json()["session_id"])

        # Cero turnos persistidos para la sesión degradada.
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(ConversationTurn)
                .where(ConversationTurn.session_id == session_id)
            )
        ).scalar_one()
        assert count == 0
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Reuso de session_id (mismo user, mismo mode) — NO crea una segunda sesion
# ---------------------------------------------------------------------------


async def test_reused_session_id_does_not_create_second_session(
    db_session: AsyncSession,
) -> None:
    """Pasar el session_id devuelto reusa la misma ChatSession (mismo id)."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="uno", model_name="gemma4"))
    fake.queue_result(_completion(text="dos", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            first = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
            assert first.status_code == 200
            session_id = first.json()["session_id"]

            second = await client.post(
                "/v1/chat",
                json={"text": "de nuevo", "mode": "vida", "session_id": session_id},
                headers=_bearer(user.id),
            )
            assert second.status_code == 200
            assert second.json()["session_id"] == session_id

        # Hay exactamente una ChatSession para ese user.
        rows = await db_session.execute(
            text("SELECT count(*) FROM sessions WHERE user_id = :uid"),
            {"uid": str(user.id)},
        )
        assert rows.scalar_one() == 1
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Auth: 401 sin token / token invalido
# ---------------------------------------------------------------------------


async def test_missing_authorization_returns_401(db_session: AsyncSession) -> None:
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post("/v1/chat", json={"text": "hola", "mode": "vida"})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_invalid_token_returns_401(db_session: AsyncSession) -> None:
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Validacion: 422 (text vacio / muy largo / mode invalido)
# ---------------------------------------------------------------------------


async def test_empty_text_returns_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_text_too_long_returns_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "x" * 4001, "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_invalid_mode_returns_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "modo-inexistente"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Aislamiento: 404 sesion de otro user
# ---------------------------------------------------------------------------


async def test_session_of_other_user_returns_404(db_session: AsyncSession) -> None:
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)

    # owner crea una sesion (commit del endpoint).
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            created = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(owner.id),
            )
            assert created.status_code == 200
            owner_session_id = created.json()["session_id"]

            # intruder intenta usar la sesion del owner -> 404.
            resp = await client.post(
                "/v1/chat",
                json={"text": "intruso", "mode": "vida", "session_id": owner_session_id},
                headers=_bearer(intruder.id),
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, owner.id)
        with suppress(Exception):
            await _delete_user(db_session, intruder.id)


# ---------------------------------------------------------------------------
# Mode mismatch: 409 (session_id de una sesion abierta en otro mode)
# ---------------------------------------------------------------------------


async def test_mode_mismatch_returns_409(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            created = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
            assert created.status_code == 200
            session_id = created.json()["session_id"]

            # Misma sesion, otro mode -> 409.
            resp = await client.post(
                "/v1/chat",
                json={"text": "ahora estudio", "mode": "estudio", "session_id": session_id},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# Rate-limit por user_id (S4): 429 tras el threshold; fail-open si Redis cae
# ---------------------------------------------------------------------------


async def test_chat_rate_limit_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N+1 turnos del mismo user -> 429 con Retry-After (mismo shape que auth).

    Bucket por user_id: con chat_max=2, 2 turnos OK reusando la misma sesion y el
    3ro da 429 ANTES de tocar la DB/LLM. ``detail`` neutro (regla #4).
    """
    monkeypatch.setattr(
        "app.core.ratelimit.get_settings",
        lambda: _chat_ratelimit_settings(chat_max=2),
    )
    monkeypatch.setattr(
        "app.api.v1.chat.get_settings",
        lambda: _chat_ratelimit_settings(chat_max=2),
    )
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    for _ in range(2):
        fake.queue_result(_completion(text="hola", model_name="gemma4"))

    store = InMemoryTokenStore()
    client = await _client(db_session, llm_client=fake, store=store)
    try:
        async with client:
            session_id: str | None = None
            for _ in range(2):
                payload: dict[str, object] = {"text": "hola", "mode": "vida"}
                if session_id is not None:
                    payload["session_id"] = session_id
                ok = await client.post("/v1/chat", json=payload, headers=_bearer(user.id))
                assert ok.status_code == 200
                session_id = ok.json()["session_id"]
            # El 3ro cruza el techo -> 429.
            r429 = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida", "session_id": session_id},
                headers=_bearer(user.id),
            )
        assert r429.status_code == 429
        assert "demasiados" in r429.json()["detail"]
        assert r429.headers.get("Retry-After") == "60"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_chat_rate_limit_fail_open(db_session: AsyncSession) -> None:
    """Con un store que degrada (Redis caído), /chat NO se bloquea (fail-open).

    El RedisTokenStore que envuelve un cliente que lanza atrapa: ``incr_with_ttl``
    => 0 (no bloquea) y ``auth_status`` => (False, False) (el token vale). Un turno
    válido sigue dando 200, nunca un 429 espurio.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))

    store = RedisTokenStore(_BoomRedisClient())
    client = await _client(db_session, llm_client=fake, store=store)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        assert resp.json()["text"] == "hola"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)
