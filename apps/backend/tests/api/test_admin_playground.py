"""Tests de INTEGRACIÓN del playground admin (F1 ADR-018).

Cubre los dos endpoints aditivos del control plane:

- ``GET /v1/admin/serving`` — inventario read-only del serving (config estática +
  salud runtime). Invariante de privacidad (regla #4): NUNCA expone ``base_url`` ni
  connection strings; con backend fake reporta ``is_real=False`` /
  ``low_perf_available=False``.
- ``POST /v1/admin/playground`` — completion ad-hoc aislada (sin DB/sesión/memoria).
  Valida el modelo (422), rechaza el backend fake (409), aplica el preset low_perf,
  y mapea la familia ``LlmError`` a status SIN ecoar el payload (regla #4: el
  ``detail`` es solo ``type(exc).__name__``).

Setup espejado de ``tests/api/test_admin_auth.py`` / ``test_chat.py``: ``httpx.AsyncClient``
+ ``ASGITransport(app=app)``, override de ``get_db`` con el ``db_session`` del fixture
(el gate admin carga el ``User``), override de ``get_llm_client`` con un ``FakeLlmClient``
programado, y patch de ``get_settings`` para forzar ``LLM_BACKEND=vllm`` (serving real)
salvo en el test del guard 409. Ningún endpoint commitea: el rollback del fixture limpia.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_llm_client
from app.core.security import create_access_token
from app.llm.clients.fakes import FakeLlmClient
from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelNotServedError,
)
from app.llm.schemas import CompletionChunk, CompletionResult, ToolCall
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.integration

# served_names reales del catálogo (ynara.config.json): gemma4 (conversational) +
# qwen (agent). El Fake del lifespan anuncia ambos.
_SERVED = frozenset({"gemma4", "qwen"})


def _real_settings() -> Settings:
    """Settings con ``LLM_BACKEND=vllm`` -> ``_wants_real_llm`` True (serving real).

    El playground guardea el backend fake con un 409; para ejercitar el camino real
    (happy-path + mapeo de errores) hay que forzar el flag SIN mentir ``environment``.
    """
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod-min-32b",
        LLM_BACKEND="vllm",
    )


def _fake_settings() -> Settings:
    """Settings con el default ``LLM_BACKEND=fake`` -> serving real NO disponible."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod-min-32b",
    )


def _completion(
    *,
    text: str = "respuesta de prueba",
    finish_reason: str = "stop",
    model_name: str = "gemma4",
) -> CompletionResult:
    """``CompletionResult`` mínimo para programar el ``FakeLlmClient``."""
    return CompletionResult(
        text=text,
        finish_reason=finish_reason,
        tool_calls=[],
        prompt_tokens=12,
        completion_tokens=7,
        model_name=model_name,
        latency_ms=33.0,
    )


async def _seed_admin(session: AsyncSession) -> User:
    """Inserta un User admin y hace flush para que tenga id asignado."""
    user = User(is_admin=True)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _client(db_session: AsyncSession, *, llm_client: FakeLlmClient) -> httpx.AsyncClient:
    """Overridea ``get_db`` + ``get_llm_client`` y devuelve el cliente ASGI.

    El caller limpia los overrides en su ``finally`` (``app.dependency_overrides.clear()``).
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: llm_client
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_settings(settings: Settings) -> Iterator[None]:
    """Patchea ``get_settings`` en el módulo playground para controlar ``_wants_real_llm``."""
    return patch("app.api.v1.admin.playground.get_settings", return_value=settings)


# ---------------------------------------------------------------------------
# GET /v1/admin/serving
# ---------------------------------------------------------------------------


async def test_serving_real_backend_inventory(db_session: AsyncSession) -> None:
    """Con LLM_BACKEND=vllm: is_real=True, low_perf_available=True, ambos modelos sanos."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.get("/v1/admin/serving", headers=_bearer(admin.id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "vllm"
        assert body["is_real"] is True
        assert body["serving_healthy"] is True
        assert body["low_perf_available"] is True
        assert body["request_timeout_s"] == 120.0
        assert body["embedder"] == "bge-m3"
        assert body["reranker"] == "bge-reranker-v2-m3"

        served_names = {m["served_name"] for m in body["models"]}
        assert served_names == {"gemma4", "qwen"}
        by_served = {m["served_name"]: m for m in body["models"]}
        # gemma4 = conversational (default_thinking False); qwen = agent (True).
        assert by_served["gemma4"]["role"] == "conversational"
        assert by_served["gemma4"]["default_thinking"] is False
        assert by_served["gemma4"]["max_model_len"] == 8192
        assert by_served["gemma4"]["tool_parser"] == "gemma4"
        assert by_served["qwen"]["role"] == "agent"
        assert by_served["qwen"]["default_thinking"] is True
        assert by_served["qwen"]["max_model_len"] == 32768
        assert by_served["qwen"]["tool_parser"] == "hermes"
        # Todos sanos: el Fake reporta healthy y sirve ambos served_names.
        assert all(m["healthy"] for m in body["models"])
        assert all(m["quantization"] == "awq_marlin" for m in body["models"])
    finally:
        app.dependency_overrides.clear()


async def test_serving_fake_backend_flags_not_real(db_session: AsyncSession) -> None:
    """Con backend fake: serving_healthy True (el Fake reporta sano) pero is_real /
    low_perf_available son False para que la UI advierta que no hay generación real."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_fake_settings()):
            async with client:
                resp = await client.get("/v1/admin/serving", headers=_bearer(admin.id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "fake"
        assert body["is_real"] is False
        assert body["low_perf_available"] is False
        assert body["serving_healthy"] is True
    finally:
        app.dependency_overrides.clear()


async def test_serving_never_exposes_base_url(db_session: AsyncSession) -> None:
    """Regla #4: la respuesta del serving NUNCA contiene base_url ni connection strings."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.get("/v1/admin/serving", headers=_bearer(admin.id))

        assert resp.status_code == 200
        # Ni el campo, ni el host de serving por default (localhost:11434).
        assert "base_url" not in resp.text
        assert "11434" not in resp.text
        assert "localhost" not in resp.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground — happy path
# ---------------------------------------------------------------------------


async def test_playground_happy_path(db_session: AsyncSession) -> None:
    """200 + PlaygroundOut con el CompletionResult del Fake; llama complete() directo."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion(text="hola desde el playground", model_name="gemma4"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "hola desde el playground"
        assert body["finish_reason"] == "stop"
        assert body["model_name"] == "gemma4"
        assert body["prompt_tokens"] == 12
        assert body["completion_tokens"] == 7
        assert body["latency_ms"] == 33.0
        # gemma4 = conversational -> default thinking False.
        assert body["thinking_used"] is False
        # Sin <think> en el text -> thinking separado es None.
        assert body["thinking"] is None

        # Trace (Fase A): 3 steps con los names del lifecycle, en orden.
        trace = body["trace"]
        assert [step["name"] for step in trace] == ["request", "thinking", "completion"]
        by_name = {step["name"]: step for step in trace}
        # request: served_name + params públicos; sin preset low_perf por default.
        assert "gemma4" in by_name["request"]["detail"]
        assert "max_tokens=1024" in by_name["request"]["detail"]
        assert "preset low_perf" not in by_name["request"]["detail"]
        # thinking off (gemma4 conversational sin override).
        assert by_name["thinking"]["detail"] == "off"
        # completion: finish_reason + tokens totales + duration_ms == latency_ms.
        assert "stop" in by_name["completion"]["detail"]
        assert "19 tok" in by_name["completion"]["detail"]  # 12 + 7
        assert by_name["completion"]["duration_ms"] == 33.0
        # request/thinking no llevan duration_ms.
        assert by_name["request"]["duration_ms"] is None
        # Regla #4: el trace NUNCA filtra system prompt ni base_url.
        assert "asistente útil" not in resp.text
        assert "base_url" not in resp.text

        # Aislamiento: se llamó complete() con el served_name, sin tools.
        assert len(fake.complete_calls) == 1
        call = fake.complete_calls[0]
        assert call["model"] == "gemma4"
        assert call["tools"] is None
        # messages = [system, user]; el user trae el mensaje del operador.
        messages = call["messages"]
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert messages[1].content == "hola"
    finally:
        app.dependency_overrides.clear()


async def test_playground_thinking_default_per_role_agent(db_session: AsyncSession) -> None:
    """qwen = agent -> default thinking True cuando el body no lo overridea."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion(model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "qwen", "message": "que onda"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        assert resp.json()["thinking_used"] is True
        assert fake.complete_calls[0]["thinking"] is True
    finally:
        app.dependency_overrides.clear()


async def test_playground_thinking_manual_override(db_session: AsyncSession) -> None:
    """El override manual del body gana sobre el default por role (gemma4 + thinking=True)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion(model_name="gemma4"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "gemma4", "message": "hola", "thinking": True},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        assert resp.json()["thinking_used"] is True
        assert fake.complete_calls[0]["thinking"] is True
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground — trace + thinking separado (Fase A)
# ---------------------------------------------------------------------------


async def test_playground_splits_thinking_block(db_session: AsyncSession) -> None:
    """Si el text del modelo trae <think>...</think>, se separa: text limpio + thinking aparte."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    raw = "<think>razonando un toque</think>Hola, esta es la respuesta final."
    fake.queue_result(_completion(text=raw, model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "qwen", "message": "hola", "thinking": True},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        body = resp.json()
        # text queda LIMPIO (sin el bloque <think>).
        assert body["text"] == "Hola, esta es la respuesta final."
        assert "<think>" not in body["text"]
        # el thinking crudo (con tags) viaja aparte.
        assert body["thinking"] == "<think>razonando un toque</think>"
        # qwen + thinking override True -> step thinking "on".
        by_name = {step["name"]: step for step in body["trace"]}
        assert by_name["thinking"]["detail"] == "on"
    finally:
        app.dependency_overrides.clear()


async def test_playground_trace_request_step_flags_low_perf(db_session: AsyncSession) -> None:
    """Con low_perf el step 'request' del trace marca el preset (detail público)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion(model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={
                        "model": "qwen",
                        "message": "hola",
                        "params": {"max_tokens": 4096, "temperature": 1.5, "low_perf": True},
                    },
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        by_name = {step["name"]: step for step in resp.json()["trace"]}
        detail = by_name["request"]["detail"]
        assert "preset low_perf" in detail
        # El preset pisa los params: el detail refleja los EFECTIVOS, no los del body.
        assert "max_tokens=256" in detail
        assert "temp=0.2" in detail
        # low_perf fuerza thinking=False.
        assert by_name["thinking"]["detail"] == "off"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground — low_perf preset
# ---------------------------------------------------------------------------


async def test_playground_low_perf_applies_preset(db_session: AsyncSession) -> None:
    """low_perf pisa max_tokens<=256, temp<=0.2 y thinking=False, sea cual sea el body."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion(model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={
                        "model": "qwen",  # agent -> default thinking True, pero low_perf lo pisa
                        "message": "hola",
                        "thinking": True,  # también pisado por el preset
                        "params": {"max_tokens": 4096, "temperature": 1.5, "low_perf": True},
                    },
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        # thinking efectivo (devuelto + pasado al cliente) forzado a False por el preset.
        assert resp.json()["thinking_used"] is False
        assert fake.complete_calls[0]["thinking"] is False
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground — validación de modelo + guard de backend fake
# ---------------------------------------------------------------------------


async def test_playground_invalid_model_422(db_session: AsyncSession) -> None:
    """Un served_name fuera del catálogo -> 422 con detail neutro 'modelo no servido'."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "no-existe", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 422
        assert resp.json()["detail"] == "modelo no servido"
        # No se intentó llamar al cliente con un modelo inválido.
        assert fake.complete_calls == []
    finally:
        app.dependency_overrides.clear()


async def test_playground_fake_backend_409(db_session: AsyncSession) -> None:
    """Con backend fake -> 409 ANTES de llamar complete() (evita la AssertionError/500)."""
    admin = await _seed_admin(db_session)
    # El Fake del lifespan NO tiene resultados encolados: si el endpoint lo llamara,
    # reventaría con AssertionError (500). El guard 409 debe cortar antes.
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_fake_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "serving real no disponible"
        assert fake.complete_calls == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground — mapeo de LlmError (sin ecoar payload, regla #4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LlmTimeoutError(), 504),
        (LlmUnavailableError(), 503),
        (LlmOverloadedError(), 503),
        (LlmContextOverflowError(), 422),
        (LlmBadRequestError(), 422),
        (ModelNotServedError(), 422),
        (LlmError(), 502),
    ],
)
async def test_playground_llm_error_mapping(
    db_session: AsyncSession, error: LlmError, expected_status: int
) -> None:
    """Cada familia de LlmError mapea a su status; el detail es solo el nombre de la clase."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_error(error)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == expected_status
        assert resp.json()["detail"] == type(error).__name__
    finally:
        app.dependency_overrides.clear()


async def test_playground_error_detail_never_echoes_payload(db_session: AsyncSession) -> None:
    """Regla #4: el detail del error NO contiene el payload crudo (str(exc)), solo el
    nombre de la clase. Aunque el LlmError lleve un ``detail`` técnico sensible, no viaja."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    secret = "PAYLOAD-SENSIBLE-1234"
    fake.queue_error(LlmTimeoutError(detail=secret))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 504
        assert resp.json()["detail"] == "LlmTimeoutError"
        # El payload sensible no aparece en NINGÚN lado de la respuesta.
        assert secret not in resp.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground/agent — tool-loop OBSERVADO (Fase B, ADR-019)
# ---------------------------------------------------------------------------


def _tool_call(name: str, arguments: dict[str, object], *, call_id: str = "call-1") -> ToolCall:
    """Una ToolCall normalizada para programar el ``FakeLlmClient`` (arguments ya dict)."""
    return ToolCall(id=call_id, name=name, arguments=arguments)


def _completion_with_tools(
    tool_calls: list[ToolCall], *, model_name: str = "qwen"
) -> CompletionResult:
    """CompletionResult con tool_calls + finish_reason NO terminal: el loop ejecuta las tools."""
    return CompletionResult(
        text="",
        finish_reason="tool_calls",
        tool_calls=tool_calls,
        prompt_tokens=20,
        completion_tokens=10,
        model_name=model_name,
        latency_ms=40.0,
    )


async def test_playground_agent_captures_tool_calls(db_session: AsyncSession) -> None:
    """200 + ``actions`` captura cada tool call observada; calendar es stub -> not_wired."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    # Iteración 1: el modelo pide una tool. Iteración 2: cierra (finish_reason terminal).
    fake.queue_result(
        _completion_with_tools(
            [
                _tool_call(
                    "calendar.create_event",
                    {
                        "title": "Reunión",
                        "start": "2026-07-01T10:00:00+00:00",
                        "end": "2026-07-01T11:00:00+00:00",
                    },
                )
            ]
        )
    )
    fake.queue_result(
        _completion(text="Listo, lo agendé.", finish_reason="stop", model_name="qwen")
    )

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/agent",
                    json={"model": "qwen", "message": "agendá una reunión el martes"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["finish_reason"] == "stop"
        assert body["model_name"] == "qwen"
        actions = body["actions"]
        assert len(actions) == 1
        assert actions[0]["name"] == "calendar.create_event"
        assert actions[0]["arguments"]["title"] == "Reunión"
        # calendar es stub no-op -> el result observado dice not_wired (cero efecto).
        assert "not_wired" in actions[0]["result"]
    finally:
        app.dependency_overrides.clear()


async def test_playground_agent_memory_tool_unreachable(db_session: AsyncSession) -> None:
    """memory.* es INALCANZABLE (sin memory_registry) -> unknown_tool, observable y sin efecto."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(
        _completion_with_tools([_tool_call("memory.update", {"id": "x", "content": "nuevo"})])
    )
    fake.queue_result(_completion(text="ok", finish_reason="stop", model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/agent",
                    json={"model": "qwen", "message": "actualizá mi memoria"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        actions = resp.json()["actions"]
        assert actions[0]["name"] == "memory.update"
        # Sin memory_registry -> la tool con write real cae en unknown_tool (sin tocar DB).
        assert "unknown_tool" in actions[0]["result"]
    finally:
        app.dependency_overrides.clear()


async def test_playground_agent_never_builds_memory_registry(db_session: AsyncSession) -> None:
    """INVARIANTE DE NO-EFECTO (ADR-019 D2): el path agente NUNCA construye memory_registry.

    Aunque el modelo pida una memory tool con write real, el endpoint pasa
    ``(default_registry(), None)``: el store de memoria no se instancia jamás. Lo
    blindamos espiando el factory -> ``call_count == 0`` es la barrera por construcción.
    """
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_result(_completion_with_tools([_tool_call("memory.delete", {"id": "x"})]))
    fake.queue_result(_completion(text="ok", finish_reason="stop", model_name="qwen"))

    client = _client(db_session, llm_client=fake)
    try:
        with (
            _patch_settings(_real_settings()),
            patch("app.llm.tools.memory.memory_registry") as mem_reg,
        ):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/agent",
                    json={"model": "qwen", "message": "borrá una memoria"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        # La barrera real (más fuerte que el ADR): el memory_registry NUNCA se construye.
        assert mem_reg.call_count == 0
    finally:
        app.dependency_overrides.clear()


async def test_playground_agent_invalid_model_422(db_session: AsyncSession) -> None:
    """Modelo fuera del catálogo -> 422 antes de correr el loop (no se llama al cliente)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/agent",
                    json={"model": "no-existe", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 422
        assert resp.json()["detail"] == "modelo no servido"
        assert fake.complete_calls == []
    finally:
        app.dependency_overrides.clear()


async def test_playground_agent_fake_backend_409(db_session: AsyncSession) -> None:
    """Backend fake -> 409 antes de correr el loop (mismo guard que /playground)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_fake_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/agent",
                    json={"model": "qwen", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "serving real no disponible"
        assert fake.complete_calls == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/admin/playground/stream — SSE token-por-token + canal reasoning
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[tuple[str, dict[str, object] | None]]:
    """Parsea el cuerpo SSE: frames ``event:``/``data:`` separados por línea en blanco."""
    events: list[tuple[str, dict[str, object] | None]] = []
    for frame in text.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        event: str | None = None
        data: dict[str, object] | None = None
        for ln in frame.splitlines():
            if ln.startswith("event:"):
                event = ln.split(":", 1)[1].strip()
            elif ln.startswith("data:"):
                data = json.loads(ln.split(":", 1)[1].strip())
        if event is not None:
            events.append((event, data))
    return events


def _chunk(
    *, text: str = "", reasoning: str | None = None, finish_reason: str | None = None
) -> CompletionChunk:
    """Un ``CompletionChunk`` para programar ``FakeLlmClient.stream`` (contenido y/o reasoning)."""
    return CompletionChunk(delta_text=text, reasoning_delta=reasoning, finish_reason=finish_reason)


async def test_playground_stream_emits_tokens_and_done(db_session: AsyncSession) -> None:
    """Cada chunk de texto -> un evento ``token``; al final un ``done`` con las métricas."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_chunks(
        [_chunk(text="Hola"), _chunk(text=", "), _chunk(text="mundo", finish_reason="stop")]
    )

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse(resp.text)
        assert [d["delta"] for ev, d in events if ev == "token"] == ["Hola", ", ", "mundo"]
        done = next(d for ev, d in events if ev == "done")
        assert done["finish_reason"] == "stop"
        assert done["model_name"] == "gemma4"
        assert done["completion_tokens"] == 3
        assert done["thinking_used"] is False
        # Sin canal reasoning ni <think> -> thinking vacío; ningún evento reasoning.
        assert not done["thinking"]
        assert all(ev != "reasoning" for ev, _ in events)
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_captures_reasoning_channel(db_session: AsyncSession) -> None:
    """qwen: el canal ``reasoning`` separado -> eventos ``reasoning`` + thinking final en ``done``.

    Reproduce el caso real (Ollama): el razonamiento llega en ``delta.reasoning`` APARTE
    del ``content``. El endpoint lo emite como eventos ``reasoning`` y lo acumula en
    ``done.thinking``; los ``completion_tokens`` cuentan SOLO los chunks de texto.
    """
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_chunks(
        [
            _chunk(reasoning="Pensando"),
            _chunk(reasoning=" el problema"),
            _chunk(text="La respuesta es 42.", finish_reason="stop"),
        ]
    )

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "qwen", "message": "pensá y respondé", "thinking": True},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert [d["delta"] for ev, d in events if ev == "reasoning"] == ["Pensando", " el problema"]
        assert [d["delta"] for ev, d in events if ev == "token"] == ["La respuesta es 42."]
        done = next(d for ev, d in events if ev == "done")
        # thinking final = el reasoning acumulado (no el content).
        assert done["thinking"] == "Pensando el problema"
        # completion_tokens cuenta SOLO el chunk de texto, no los de reasoning.
        assert done["completion_tokens"] == 1
        assert done["thinking_used"] is True
        # el thinking pasado al cliente fue True (qwen agent + override).
        assert fake.stream_calls[0]["thinking"] is True
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_reasoning_only_empty_answer(db_session: AsyncSession) -> None:
    """El caso que confundía: qwen gasta el budget razonando y no emite texto.

    Sin chunks de ``content`` el answer queda vacío (``completion_tokens == 0``) pero el
    razonamiento SÍ se captura: eventos ``reasoning`` + ``done.thinking`` poblado.
    """
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_chunks(
        [_chunk(reasoning="Sigo pensando"), _chunk(reasoning="…", finish_reason="length")]
    )

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "qwen", "message": "pensá mucho", "thinking": True},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert [d["delta"] for ev, d in events if ev == "reasoning"] == ["Sigo pensando", "…"]
        assert all(ev != "token" for ev, _ in events)
        done = next(d for ev, d in events if ev == "done")
        assert done["completion_tokens"] == 0
        assert done["finish_reason"] == "length"
        assert done["thinking"] == "Sigo pensando…"
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_inline_think_block(db_session: AsyncSession) -> None:
    """Fallback: si el modelo embebe <think>...</think> en el ``content`` (vLLM sin
    reasoning-parser), el thinking final se separa de ahí (precedencia: reasoning > inline)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    fake.queue_chunks(
        [
            _chunk(text="<think>razonando</think>"),
            _chunk(text="Respuesta final.", finish_reason="stop"),
        ]
    )

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "qwen", "message": "hola", "thinking": True},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        done = next(d for ev, d in events if ev == "done")
        # Sin canal reasoning -> se separa el <think> del content acumulado.
        assert done["thinking"] == "<think>razonando</think>"
        assert all(ev != "reasoning" for ev, _ in events)
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_error_event_neutral(db_session: AsyncSession) -> None:
    """Un LlmError a mitad del stream -> evento ``error`` con mensaje NEUTRO (regla #4)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)
    secret = "PAYLOAD-SENSIBLE-9999"
    fake.queue_stream_error(LlmTimeoutError(detail=secret))

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        # El stream ya abrió (200): el error viaja como evento SSE, no como status.
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        error = next(d for ev, d in events if ev == "error")
        assert error["code"] == "stream_error"
        # Regla #4: ni el payload sensible ni el nombre de la clase viajan.
        assert secret not in resp.text
        assert "LlmTimeoutError" not in resp.text
        # No se emite done tras el error.
        assert all(ev != "done" for ev, _ in events)
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_invalid_model_422(db_session: AsyncSession) -> None:
    """Modelo fuera del catálogo -> 422 HTTP (no SSE), antes de abrir el stream."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_real_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "no-existe", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 422
        assert resp.json()["detail"] == "modelo no servido"
        assert fake.stream_calls == []
    finally:
        app.dependency_overrides.clear()


async def test_playground_stream_fake_backend_409(db_session: AsyncSession) -> None:
    """Backend fake -> 409 HTTP antes de abrir el stream (mismo guard que el sync)."""
    admin = await _seed_admin(db_session)
    fake = FakeLlmClient(served_models=_SERVED)

    client = _client(db_session, llm_client=fake)
    try:
        with _patch_settings(_fake_settings()):
            async with client:
                resp = await client.post(
                    "/v1/admin/playground/stream",
                    json={"model": "gemma4", "message": "hola"},
                    headers=_bearer(admin.id),
                )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "serving real no disponible"
        assert fake.stream_calls == []
    finally:
        app.dependency_overrides.clear()
