"""Tests E2E del endpoint ``POST /v1/chat/stream`` (M9 Ola 3).

Espeja ``tests/api/test_chat.py`` (mismos helpers ``_seed_user`` /
``_delete_user`` / ``_bearer`` / ``_completion`` / ``_client``, mismo patron de
``dependency_overrides[get_db]`` + Fakes, misma limpieza en ``finally``) y le
suma un mini-parser SSE local (``_parse_sse``) que ESPEJA la logica de
``packages/shared-schemas/src/sse.ts`` (el test backend no puede importar el
parser TS). El wire que produce el endpoint DEBE satisfacer ese parser.

Todos son ``integration`` (tocan la DB de tests dedicada: el endpoint hace
``session.commit()``). Ejercitan el stack completo HTTP -> deps -> router con
clientes Fake, sin red ni Redis.

``ASGITransport`` BUFFEREA el ``StreamingResponse`` entero, asi que
``await client.post('/v1/chat/stream', ...)`` ya da ``resp.text`` con el wire
SSE completo: NO hace falta ``client.stream()``.

Cubre: happy path Gemma (tokens + done) y Qwen (actions en done), reuso de
sesion, mapeo de errores HTTP normales (401/422/404/409, NUNCA como eventos
SSE), los invariantes del wire (``''.join(deltas) == text``, todo bloque cierra
en ``\\n\\n``, ningun newline crudo parte el bloque), la coercion de
``finish_reason`` (None -> ``stop``, ``degraded`` preservado) y el 500 limpio
sin stream parcial cuando el commit falla.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.llm.errors import LlmBadRequestError
from app.llm.schemas import ChatResponse, CompletionResult, ToolCall
from app.main import app
from app.models.session import ChatSession
from app.models.user import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers (espejo EXACTO de tests/api/test_chat.py)
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
    """Overridea las deps y devuelve un AsyncClient ASGI (espejo de test_chat).

    El caller usa el cliente dentro de ``async with`` y limpia los overrides en
    su ``finally`` via ``app.dependency_overrides.clear()``.
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
# Mini-parser SSE local — ESPEJA packages/shared-schemas/src/sse.ts
# ---------------------------------------------------------------------------


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    """Parsea un wire SSE completo a ``[(event_name, data_dict), ...]``.

    Espeja la logica de ``sse.ts``: normaliza CRLF, separa bloques por
    ``\\n\\n``, ignora lineas de comentario (``:``) y vacias, extrae ``event:``
    y ``data:`` (strippeando un espacio opcional tras ``data:``), saltea bloques
    sin data o con ``[DONE]``, y hace ``json.loads`` del data. Lanza
    ``json.JSONDecodeError`` si un bloque con evento conocido trae data rota (lo
    que en ``sse.ts`` seria un ``SseParseError``).
    """
    normalized = raw.replace("\r\n", "\n")
    events: list[tuple[str, dict]] = []
    for block in normalized.split("\n\n"):
        if block.strip() == "":
            continue
        event_name: str | None = None
        data_lines: list[str] = []
        for raw_line in block.split("\n"):
            line = raw_line.rstrip("\r")
            if line == "" or line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                # El valor arranca tras "data:" + un espacio opcional.
                value = line[len("data:") :]
                if value.startswith(" "):
                    value = value[1:]
                data_lines.append(value)
        if event_name is None:
            continue
        data_text = "\n".join(data_lines)
        if data_text == "" or data_text == "[DONE]":
            continue
        events.append((event_name, json.loads(data_text)))
    return events


def _deltas(events: list[tuple[str, dict]]) -> list[str]:
    """Los ``delta`` de los eventos ``token``, en orden."""
    return [d["delta"] for (name, d) in events if name == "token"]


def _done(events: list[tuple[str, dict]]) -> dict:
    """El unico dict del evento ``done``."""
    dones = [d for (name, d) in events if name == "done"]
    assert len(dones) == 1, f"se esperaba exactamente 1 done, hubo {len(dones)}"
    return dones[0]


# ---------------------------------------------------------------------------
# 1. Happy path: Gemma (vida) — tokens + done, sesion persistida
# ---------------------------------------------------------------------------


async def test_happy_gemma_tokens_y_done(db_session: AsyncSession) -> None:
    """200 + tokens que reconstruyen el texto + done con actions vacias."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola, todo bien?", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(resp.text)
        deltas = _deltas(events)
        assert "".join(deltas) == "hola, todo bien?"
        assert len(deltas) >= 1

        done = _done(events)
        assert done["actions"] == []
        assert done["finish_reason"] == "stop"
        assert done["session_id"]
        returned_id = uuid.UUID(done["session_id"])

        cs = await db_session.get(ChatSession, returned_id)
        assert cs is not None
        assert cs.user_id == user.id
        assert cs.mode == Mode.VIDA
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 2. Happy path: Qwen (productividad) — actions pobladas en el done
# ---------------------------------------------------------------------------


async def test_happy_qwen_actions_en_done(db_session: AsyncSession) -> None:
    """200 + actions en done (tool loop). Encola consolidacion (mockeada)."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"qwen"}))
    # Vuelta 1: tool_call memory.search; vuelta 2: stop con texto.
    tc = ToolCall(id="tc-1", name="memory.search", arguments={"query": "reuniones"})
    fake.queue_result(
        _completion(text="", finish_reason="tool_calls", tool_calls=[tc], model_name="qwen")
    )
    fake.queue_result(_completion(text="Listo", finish_reason="stop", model_name="qwen"))

    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.llm.router.consolidate_turn") as mock_task:
            mock_task.delay = MagicMock()
            async with client:
                resp = await client.post(
                    "/v1/chat/stream",
                    json={"text": "agenda una reunion", "mode": "productividad"},
                    headers=_bearer(user.id),
                )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert "".join(_deltas(events)) == "Listo"

        done = _done(events)
        assert done["finish_reason"] == "stop"
        assert len(done["actions"]) >= 1
        action = done["actions"][0]
        assert set(action.keys()) == {"id", "name", "arguments", "result"}
        assert action["id"] == "tc-1"
        assert action["name"] == "memory.search"
        assert action["arguments"] == {"query": "reuniones"}
        # Qwen escribe memoria -> se encolo la consolidacion.
        mock_task.delay.assert_called_once()
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 3. Reuso de session_id (mismo user, mismo mode) — no crea segunda sesion
# ---------------------------------------------------------------------------


async def test_reuso_session_id(db_session: AsyncSession) -> None:
    """El session_id devuelto reusa la misma ChatSession (mismo id)."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="uno", model_name="gemma4"))
    fake.queue_result(_completion(text="dos", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            first = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
            assert first.status_code == 200
            first_id = _done(_parse_sse(first.text))["session_id"]

            second = await client.post(
                "/v1/chat/stream",
                json={"text": "de nuevo", "mode": "vida", "session_id": first_id},
                headers=_bearer(user.id),
            )
            assert second.status_code == 200
            second_id = _done(_parse_sse(second.text))["session_id"]
            assert second_id == first_id

        rows = await db_session.execute(
            text("SELECT count(*) FROM sessions WHERE user_id = :uid"),
            {"uid": str(user.id)},
        )
        assert rows.scalar_one() == 1
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 4-5. Auth: 401 sin token / token invalido (HTTP normal, NO evento SSE)
# ---------------------------------------------------------------------------


async def test_missing_auth_401(db_session: AsyncSession) -> None:
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post("/v1/chat/stream", json={"text": "hola", "mode": "vida"})
        assert resp.status_code == 401
        # 401 es HTTP normal, NO un evento SSE error.
        assert not resp.headers["content-type"].startswith("text/event-stream")
    finally:
        app.dependency_overrides.clear()


async def test_invalid_token_401(db_session: AsyncSession) -> None:
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6-8. Validacion: 422 (text vacio / muy largo / mode invalido)
# ---------------------------------------------------------------------------


async def test_empty_text_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_text_too_long_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "x" * 4001, "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


async def test_invalid_mode_422(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "modo-inexistente"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 9. Aislamiento: 404 sesion de otro user (HTTP, no evento SSE error)
# ---------------------------------------------------------------------------


async def test_session_otro_user_404(db_session: AsyncSession) -> None:
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)

    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            created = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(owner.id),
            )
            assert created.status_code == 200
            owner_session_id = _done(_parse_sse(created.text))["session_id"]

            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "intruso", "mode": "vida", "session_id": owner_session_id},
                headers=_bearer(intruder.id),
            )
        assert resp.status_code == 404
        # 404 es HTTP normal, NO un evento SSE error.
        assert not resp.headers["content-type"].startswith("text/event-stream")
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, owner.id)
        with suppress(Exception):
            await _delete_user(db_session, intruder.id)


# ---------------------------------------------------------------------------
# 10. Mode mismatch: 409 (session_id de una sesion abierta en otro mode)
# ---------------------------------------------------------------------------


async def test_mode_mismatch_409(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))
    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            created = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
            assert created.status_code == 200
            session_id = _done(_parse_sse(created.text))["session_id"]

            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "ahora estudio", "mode": "estudio", "session_id": session_id},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 11. Invariante ''.join(deltas) == text para textos hostiles al wire SSE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload_text",
    [
        "linea1\nlinea2",
        "crlf\r\nfin",
        "cr\rfin",
        "doble\n\nbloque",
        "a   b",
        "hola 👋 mundo",
        "你好世界",
    ],
)
async def test_invariante_join_igual_text(
    db_session: AsyncSession, payload_text: str
) -> None:
    """El wire nunca se parte por newlines: ''.join(deltas) == text EXACTO."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text=payload_text, model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        # _parse_sse no debe lanzar: el wire no se parte por los newlines crudos.
        events = _parse_sse(resp.text)
        assert "".join(_deltas(events)) == payload_text
        # Hay un done parseable al final.
        assert _done(events)["finish_reason"] == "stop"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 12. finish_reason None coerciona a 'stop'
# ---------------------------------------------------------------------------


async def test_finish_reason_none_coerciona_stop(db_session: AsyncSession) -> None:
    """resp.finish_reason None -> done.finish_reason == 'stop' (coercion D4).

    Se parchea ``route`` (importado en el endpoint como ``app.api.v1.chat.route``)
    para devolver un ``ChatResponse`` con ``finish_reason=None``: el path natural
    del tool loop nunca deja None (siempre un string), asi que forzarlo en el
    borde del router es la unica forma honesta de ejercitar la coercion.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))

    none_resp = ChatResponse(
        text="respuesta",
        actions=[],
        session_id="opaco",
        finish_reason=None,
    )
    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.api.v1.chat.route", new=AsyncMock(return_value=none_resp)):
            async with client:
                resp = await client.post(
                    "/v1/chat/stream",
                    json={"text": "hola", "mode": "vida"},
                    headers=_bearer(user.id),
                )
        assert resp.status_code == 200
        done = _done(_parse_sse(resp.text))
        assert done["finish_reason"] == "stop"
        assert isinstance(done["finish_reason"], str)
        assert done["finish_reason"] != ""
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 13. finish_reason 'degraded' se preserva (fallback de route)
# ---------------------------------------------------------------------------


async def test_finish_reason_degraded_se_preserva(db_session: AsyncSession) -> None:
    """El fallback de route (LlmBadRequestError) deja finish_reason 'degraded'.

    El Fake encola un ``LlmBadRequestError``: ``run_tool_loop`` lo propaga,
    ``route`` lo captura y devuelve ``finish_reason='degraded'``. El stream lo
    preserva tal cual (NO lo coerciona a 'stop') y NO emite evento error: es una
    respuesta 200 valida con texto de fallback.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_error(LlmBadRequestError())

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        done = _done(events)
        assert done["finish_reason"] == "degraded"
        # NO hay evento error: es una respuesta degradada valida, no un fallo.
        assert all(name != "error" for (name, _) in events)
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 14. text vacio -> 0 tokens + exactamente 1 done
# ---------------------------------------------------------------------------


async def test_text_vacio_cero_tokens_un_done(db_session: AsyncSession) -> None:
    """Con text vacio el for no itera: 0 tokens, 1 done parseable (D7).

    Se parchea ``route`` para devolver ``text=''``: ``route`` real nunca devuelve
    vacio (``run_tool_loop`` usa fallback_text), asi que el path text-vacio se
    fuerza en el borde del router.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))

    empty_resp = ChatResponse(text="", actions=[], session_id="opaco", finish_reason="stop")
    client = await _client(db_session, llm_client=fake)
    try:
        with patch("app.api.v1.chat.route", new=AsyncMock(return_value=empty_resp)):
            async with client:
                resp = await client.post(
                    "/v1/chat/stream",
                    json={"text": "hola", "mode": "vida"},
                    headers=_bearer(user.id),
                )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert len(_deltas(events)) == 0
        # Exactamente 1 done parseable.
        assert _done(events)["finish_reason"] == "stop"
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 15. Estructura del wire crudo
# ---------------------------------------------------------------------------


async def test_wire_estructura(db_session: AsyncSession) -> None:
    """El wire arranca con 'event: token\\ndata: ', cierra en '\\n\\n', parsea ok."""
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola mundo", model_name="gemma4"))

    client = await _client(db_session, llm_client=fake)
    try:
        async with client:
            resp = await client.post(
                "/v1/chat/stream",
                json={"text": "hola", "mode": "vida"},
                headers=_bearer(user.id),
            )
        assert resp.status_code == 200
        raw = resp.text
        # Texto no vacio -> arranca con el primer token.
        assert raw.startswith("event: token\ndata: ")
        # Todo bloque (incluido el ultimo) cierra en '\n\n'.
        assert raw.endswith("\n\n")
        # Parsea sin lanzar: [...tokens, done].
        events = _parse_sse(raw)
        assert [name for (name, _) in events] == [
            *["token"] * len(_deltas(events)),
            "done",
        ]
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)


# ---------------------------------------------------------------------------
# 16. commit falla -> 500 sin stream parcial (0 eventos token en el body)
# ---------------------------------------------------------------------------


async def test_commit_falla_500_sin_stream_parcial(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si session.commit() falla, el turno revienta ANTES del StreamingResponse.

    El commit ocurre dentro de ``_run_chat_turn``, ANTES de construir el
    ``StreamingResponse``: si lanza, la excepcion propaga como 500 (get_db hace
    rollback) y el stream NUNCA arranco -> 0 bytes SSE en el body. Se mockea el
    ``commit`` del MISMO ``db_session`` que cede el override, para fallar el
    commit puntual del endpoint sin romper la limpieza posterior.

    Nota de transporte: el ``_client`` helper espeja test_chat.py y usa el
    default ``raise_app_exceptions=True``, que re-lanza la excepcion del server
    al caller en vez de mapearla a un 500 (no hay rama 500 en los tests de
    /chat). Aca SI queremos ver el 500 que un cliente HTTP real veria, asi que
    se construye un ASGITransport dedicado con ``raise_app_exceptions=False``
    (deja que ServerErrorMiddleware de Starlette emita el 500), sin tocar el
    helper compartido.
    """
    user = await _seed_user(db_session)
    fake = FakeLlmClient(served_models=frozenset({"gemma4"}))
    fake.queue_result(_completion(text="hola", model_name="gemma4"))

    async def _boom() -> None:
        raise RuntimeError("commit boom")

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: fake
    app.dependency_overrides[get_embedder] = FakeEmbeddingClient
    app.dependency_overrides[get_reranker] = FakeReranker
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with patch.object(db_session, "commit", new=AsyncMock(side_effect=_boom)):
            async with client:
                resp = await client.post(
                    "/v1/chat/stream",
                    json={"text": "hola", "mode": "vida"},
                    headers=_bearer(user.id),
                )
        assert resp.status_code == 500
        # El stream nunca arranco: no hay eventos token (ni SSE) en el body.
        assert "event: token" not in resp.text
        assert not resp.headers["content-type"].startswith("text/event-stream")
    finally:
        app.dependency_overrides.clear()
        await _delete_user(db_session, user.id)
