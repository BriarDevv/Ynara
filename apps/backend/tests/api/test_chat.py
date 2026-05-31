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
- ``app.llm.router.consolidate_turn`` se parchea (Qwen encola; no hay Redis).

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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_llm_client, get_reranker
from app.core.security import create_access_token
from app.enums import Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.reranker import FakeReranker
from app.llm.schemas import CompletionResult, ToolCall
from app.main import app
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
) -> AsyncIterator[httpx.AsyncClient]:
    """Context-ish helper: overridea las deps y devuelve un AsyncClient ASGI.

    El caller debe usar el cliente dentro de ``async with`` y limpiar los
    overrides despues (lo hace cada test en su ``finally`` via
    ``app.dependency_overrides.clear()``).
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: llm_client
    app.dependency_overrides[get_embedder] = FakeEmbeddingClient
    app.dependency_overrides[get_reranker] = FakeReranker
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


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
        with patch("app.llm.router.consolidate_turn") as mock_task:
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
        # Qwen escribe memoria -> se encolo la consolidacion.
        mock_task.delay.assert_called_once()
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
