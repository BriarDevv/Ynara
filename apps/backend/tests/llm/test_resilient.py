"""Tests del ``ResilientClient`` (M3).

Inyectan un ``sleep`` fake async (que registra los delays, sin dormir de
verdad) y un ``clock`` fake. El doble de instancia es ``FakeLlmClient``,
que programa resultados / errores por cliente. El pool se arma a mano para
controlar el orden primario -> secundario on-prem.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.llm.clients.circuit import CircuitBreaker, CircuitState
from app.llm.clients.fakes import FakeLlmClient
from app.llm.clients.pool import ClientPool, FirstHealthy
from app.llm.clients.resilient import ResilientClient
from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmError,
    LlmTimeoutError,
    LlmUnavailableError,
)
from app.llm.schemas import ChatMessage, CompletionResult, ModelHealth

_MODEL = "qwen-3.5-9b"


class _Clock:
    """Reloj fake controlable."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _FakeSleep:
    """``sleep`` async fake: registra cada delay, no duerme."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _result(text: str = "ok") -> CompletionResult:
    return CompletionResult(
        text=text,
        finish_reason="stop",
        prompt_tokens=1,
        completion_tokens=1,
        model_name=_MODEL,
        latency_ms=0.0,
    )


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="hola")]


def _fake(model: str = _MODEL) -> FakeLlmClient:
    return FakeLlmClient(served_models=frozenset({model}))


def _resilient(
    clients: list[FakeLlmClient],
    *,
    sleep: _FakeSleep | None = None,
    clock: _Clock | None = None,
    max_attempts: int = 3,
    breaker_factory: object | None = None,
) -> ResilientClient:
    pool = ClientPool(list(clients), FirstHealthy())
    kwargs: dict[str, object] = {
        "max_attempts": max_attempts,
        "sleep": sleep or _FakeSleep(),
        "clock": clock or _Clock(),
    }
    if breaker_factory is not None:
        kwargs["breaker_factory"] = breaker_factory
    return ResilientClient(pool, **kwargs)  # type: ignore[arg-type]


# ---------- health agregado ----------


class _HealthExploding:
    """Cliente cuyo health() revienta (no se programa con FakeLlmClient)."""

    async def health(self) -> ModelHealth:
        raise RuntimeError("health boom")


async def test_health_skips_client_that_raises() -> None:
    """Un cliente que rompe en health() no debe tumbar el chequeo agregado."""
    pool = ClientPool([_HealthExploding(), _fake()], FirstHealthy())  # type: ignore[list-item]
    resilient = ResilientClient(pool)
    health = await resilient.health()
    assert health.healthy is True


async def test_health_all_raise_returns_unhealthy_not_exception() -> None:
    """Si todos rompen en health(), devuelve no-sano (nunca propaga)."""
    pool = ClientPool([_HealthExploding(), _HealthExploding()], FirstHealthy())  # type: ignore[list-item]
    resilient = ResilientClient(pool)
    health = await resilient.health()
    assert health.healthy is False


# ---------- exito directo ----------


async def test_direct_success() -> None:
    client = _fake()
    client.queue_result(_result("hola"))
    sleep = _FakeSleep()
    resilient = _resilient([client], sleep=sleep)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "hola"
    assert result.finish_reason == "stop"
    assert sleep.delays == []  # sin reintentos -> sin sleeps


# ---------- transitorio -> reintenta -> exito ----------


async def test_transient_then_success_retries() -> None:
    client = _fake()
    client.queue_error(LlmTimeoutError())
    client.queue_error(LlmUnavailableError())
    client.queue_result(_result("recuperado"))
    sleep = _FakeSleep()
    resilient = _resilient([client], sleep=sleep, max_attempts=3)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "recuperado"
    assert len(client.complete_calls) == 3  # 2 fallos + 1 exito
    assert len(sleep.delays) == 2  # un sleep entre cada reintento, no tras el ultimo
    assert all(d >= 0.0 for d in sleep.delays)


async def test_no_sleep_after_last_attempt() -> None:
    client = _fake()
    client.queue_error(LlmTimeoutError())
    client.queue_error(LlmTimeoutError())
    sleep = _FakeSleep()
    resilient = _resilient([client], sleep=sleep, max_attempts=2)
    await resilient.complete(model=_MODEL, messages=_messages())
    # 2 intentos -> un solo sleep (entre el 1ro y el 2do), no tras agotar.
    assert len(sleep.delays) == 1


# ---------- todos fallan -> degradado ----------


async def test_all_fail_returns_degraded() -> None:
    client = _fake()
    for _ in range(3):
        client.queue_error(LlmTimeoutError())
    resilient = _resilient([client], max_attempts=3)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.finish_reason == "degraded"
    assert result.model_name == _MODEL
    assert result.text


async def test_degraded_text_is_custom() -> None:
    client = _fake()
    client.queue_error(LlmTimeoutError())
    pool = ClientPool([client], FirstHealthy())
    resilient = ResilientClient(
        pool,
        max_attempts=1,
        sleep=_FakeSleep(),
        clock=_Clock(),
        degraded_text="texto custom",
    )
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "texto custom"
    assert result.finish_reason == "degraded"


# ---------- error permanente -> se re-lanza sin fallback ----------


async def test_permanent_error_reraised_without_fallback() -> None:
    primary = _fake()
    primary.queue_error(LlmBadRequestError())
    secondary = _fake()
    secondary.queue_result(_result("no deberia usarse"))
    resilient = _resilient([primary, secondary])
    with pytest.raises(LlmBadRequestError):
        await resilient.complete(model=_MODEL, messages=_messages())
    # el secundario nunca se toco: el error es del request, no de la infra.
    assert secondary.complete_calls == []
    assert len(primary.complete_calls) == 1  # sin reintentos en permanente


# ---------- LlmError de infra no clasificado -> fallback-able, degrada ----------


async def test_unclassified_llm_error_degrades() -> None:
    # LlmError base (4xx no mapeado / "respuesta sin choices" del VllmClient
    # real) no es permanente: debe ser fallback-able y terminar degradado,
    # nunca escaparse cruda al caller (contrato central de M3 + regla #4).
    client = _fake()
    for _ in range(3):
        client.queue_error(LlmError("respuesta sin choices"))
    resilient = _resilient([client], max_attempts=3)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.finish_reason == "degraded"


async def test_unclassified_error_falls_back_to_secondary() -> None:
    primary = _fake()
    primary.queue_error(LlmError("HTTP 404"))
    secondary = _fake()
    secondary.queue_result(_result("desde secundario"))
    resilient = _resilient([primary, secondary], max_attempts=1)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "desde secundario"
    assert len(secondary.complete_calls) == 1


# ---------- fallback on-prem: primario falla -> usa secundario ----------


async def test_primary_fails_uses_secondary() -> None:
    primary = _fake()
    for _ in range(3):
        primary.queue_error(LlmUnavailableError())
    secondary = _fake()
    secondary.queue_result(_result("desde secundario"))
    resilient = _resilient([primary, secondary], max_attempts=3)
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "desde secundario"
    assert len(primary.complete_calls) == 3  # agoto reintentos
    assert len(secondary.complete_calls) == 1


# ---------- breaker abre y saltea el client ----------


async def test_breaker_opens_and_skips_client() -> None:
    primary = _fake()
    secondary = _fake()
    # breaker con threshold=1: un fallo del candidato lo abre.
    factory = lambda: CircuitBreaker(failure_threshold=1, recovery_timeout_s=30.0)  # noqa: E731

    # Primera llamada: el primario falla (agota reintentos) -> breaker abre,
    # cae al secundario que responde OK.
    primary.queue_error(LlmTimeoutError())
    secondary.queue_result(_result("secundario-1"))
    resilient = _resilient([primary, secondary], max_attempts=1, breaker_factory=factory)
    first = await resilient.complete(model=_MODEL, messages=_messages())
    assert first.text == "secundario-1"
    assert len(primary.complete_calls) == 1

    # Segunda llamada: el primario tiene el breaker OPEN -> se saltea sin
    # tocarlo; va directo al secundario.
    secondary.queue_result(_result("secundario-2"))
    second = await resilient.complete(model=_MODEL, messages=_messages())
    assert second.text == "secundario-2"
    assert len(primary.complete_calls) == 1  # no se volvio a llamar
    assert len(secondary.complete_calls) == 2


async def test_breaker_recovers_after_timeout() -> None:
    primary = _fake()
    clock = _Clock()
    factory = lambda: CircuitBreaker(  # noqa: E731
        failure_threshold=1, recovery_timeout_s=30.0, clock=clock
    )
    primary.queue_error(LlmTimeoutError())  # 1er fallo abre el breaker
    resilient = _resilient([primary], max_attempts=1, clock=clock, breaker_factory=factory)
    degraded = await resilient.complete(model=_MODEL, messages=_messages())
    assert degraded.finish_reason == "degraded"  # solo el primario, abrio

    # avanzamos el clock para que el breaker pase a HALF_OPEN y deje probar.
    clock.now = 30.0
    primary.queue_result(_result("recuperado"))
    recovered = await resilient.complete(model=_MODEL, messages=_messages())
    assert recovered.text == "recuperado"


# ---------- breaker abierto en todos -> degradado sin llamar ----------


async def test_all_breakers_open_returns_degraded_without_calls() -> None:
    primary = _fake()
    factory = lambda: CircuitBreaker(failure_threshold=1, recovery_timeout_s=999.0)  # noqa: E731
    primary.queue_error(LlmTimeoutError())
    resilient = _resilient([primary], max_attempts=1, breaker_factory=factory)
    await resilient.complete(model=_MODEL, messages=_messages())  # abre el breaker
    calls_after_open = len(primary.complete_calls)

    # ahora el breaker esta OPEN: la proxima no debe tocar al cliente.
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.finish_reason == "degraded"
    assert len(primary.complete_calls) == calls_after_open


# ---------- deadline global (P2.5) ----------


class _SlowClient:
    """Cliente cuyo ``complete`` duerme ``delay_s`` real antes de responder.

    Sirve para verificar el deadline global del ``ResilientClient`` sin
    depender de timeouts HTTP reales.
    """

    def __init__(self, *, delay_s: float, model: str = _MODEL) -> None:
        self._delay_s = delay_s
        self._model = model
        self.complete_calls = 0

    def serves_model(self, model: str) -> bool:
        return model == self._model

    async def complete(self, **_kwargs: object) -> CompletionResult:
        self.complete_calls += 1
        await asyncio.sleep(self._delay_s)
        return _result("tarde")

    async def health(self) -> ModelHealth:
        return ModelHealth(model_name=self._model, healthy=True)


async def test_global_budget_degrades_within_budget() -> None:
    # Un cliente que tarda mucho mas que el budget global debe degradar al
    # vencerse el deadline, no tras sumar el timeout de cada intento.
    slow = _SlowClient(delay_s=5.0)
    pool = ClientPool([slow], FirstHealthy())  # type: ignore[list-item]
    resilient = ResilientClient(
        pool,
        max_attempts=3,
        total_budget_s=0.05,
        sleep=_FakeSleep(),
        clock=_Clock(),
    )

    started = time.monotonic()
    result = await resilient.complete(model=_MODEL, messages=_messages())
    elapsed = time.monotonic() - started

    assert result.finish_reason == "degraded"
    assert result.model_name == _MODEL
    # Degrada cerca del budget, muy por debajo del delay del cliente (5s).
    assert elapsed < 1.0


async def test_global_budget_does_not_sum_all_candidates() -> None:
    # Con dos clientes lentos y max_attempts alto, el peor caso sin budget seria
    # delay x attempts x candidatos. El budget corta antes de recorrerlos.
    slow_primary = _SlowClient(delay_s=5.0)
    slow_secondary = _SlowClient(delay_s=5.0)
    pool = ClientPool([slow_primary, slow_secondary], FirstHealthy())  # type: ignore[list-item]
    resilient = ResilientClient(
        pool,
        max_attempts=5,
        total_budget_s=0.05,
        sleep=_FakeSleep(),
        clock=_Clock(),
    )

    started = time.monotonic()
    result = await resilient.complete(model=_MODEL, messages=_messages())
    elapsed = time.monotonic() - started

    assert result.finish_reason == "degraded"
    assert elapsed < 1.0
    # No llego a recorrer todos los intentos de todos los candidatos.
    assert slow_primary.complete_calls + slow_secondary.complete_calls < 5 * 2


async def test_within_budget_returns_normal_result() -> None:
    # Camino feliz: si el cliente responde dentro del budget, el resultado pasa
    # sin tocar la ruta degradada.
    client = _fake()
    client.queue_result(_result("a tiempo"))
    pool = ClientPool([client], FirstHealthy())
    resilient = ResilientClient(
        pool,
        total_budget_s=5.0,
        sleep=_FakeSleep(),
        clock=_Clock(),
    )
    result = await resilient.complete(model=_MODEL, messages=_messages())
    assert result.text == "a tiempo"
    assert result.finish_reason == "stop"


async def test_global_budget_does_not_swallow_permanent_error() -> None:
    # Un error PERMANENTE (overflow) lanzado dentro de un candidato debe PROPAGAR
    # aun con el budget global activo: el asyncio.timeout solo coerce a degradado
    # su PROPIO TimeoutError, NUNCA un LlmContextOverflowError (no es Timeout).
    client = _fake()
    client.queue_error(LlmContextOverflowError("contexto excedido"))
    pool = ClientPool([client], FirstHealthy())
    resilient = ResilientClient(pool, total_budget_s=5.0, sleep=_FakeSleep(), clock=_Clock())

    with pytest.raises(LlmContextOverflowError):
        await resilient.complete(model=_MODEL, messages=_messages())


# ---------- aclose (teardown) ----------


class _ClosableClient:
    """Cliente minimo que registra su cierre (proxy del VllmClient real)."""

    def __init__(self) -> None:
        self.closed = False

    def serves_model(self, model: str) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


async def test_aclose_closes_every_pool_client() -> None:
    # El teardown del lifespan cierra el ResilientClient -> debe cerrar CADA
    # cliente del pool (sus httpx.AsyncClient en prod), sin filtrar conexiones.
    c1, c2 = _ClosableClient(), _ClosableClient()
    pool = ClientPool([c1, c2], FirstHealthy())  # type: ignore[list-item]
    resilient = ResilientClient(pool)

    await resilient.aclose()

    assert c1.closed is True
    assert c2.closed is True


# ---------- serves_model / health ----------


def test_serves_model_aggregates_pool() -> None:
    resilient = _resilient([_fake(_MODEL)])
    assert resilient.serves_model(_MODEL) is True
    assert resilient.serves_model("otro") is False


async def test_health_healthy_if_any_client_up() -> None:
    down = _fake()
    down.set_health(False)
    up = _fake()
    up.set_health(True)
    resilient = _resilient([down, up])
    health = await resilient.health()
    assert health.healthy is True


async def test_health_unhealthy_if_all_down() -> None:
    a = _fake()
    a.set_health(False)
    b = _fake()
    b.set_health(False)
    resilient = _resilient([a, b])
    health = await resilient.health()
    assert health.healthy is False
    assert health.model_name == _MODEL


# ---------- streaming ----------


async def test_stream_delegates_to_candidate() -> None:
    from app.llm.schemas import CompletionChunk

    client = _fake()
    client.queue_chunks([CompletionChunk(delta_text="ho"), CompletionChunk(delta_text="la")])
    resilient = _resilient([client])
    chunks = [c async for c in resilient.stream(model=_MODEL, messages=_messages())]
    assert "".join(c.delta_text for c in chunks) == "hola"


async def test_stream_skips_open_breaker() -> None:
    from app.llm.schemas import CompletionChunk

    primary = _fake()
    secondary = _fake()
    factory = lambda: CircuitBreaker(failure_threshold=1, recovery_timeout_s=999.0)  # noqa: E731
    primary.queue_error(LlmTimeoutError())
    secondary.queue_result(_result("x"))
    resilient = _resilient([primary, secondary], max_attempts=1, breaker_factory=factory)
    # abre el breaker del primario via un complete fallido.
    await resilient.complete(model=_MODEL, messages=_messages())

    # el stream debe elegir el secundario (breaker del primario OPEN).
    secondary.queue_chunks([CompletionChunk(delta_text="ok")])
    chunks = [c async for c in resilient.stream(model=_MODEL, messages=_messages())]
    assert "".join(c.delta_text for c in chunks) == "ok"
    assert secondary.stream_calls
    assert primary.stream_calls == []


async def test_stream_all_breakers_open_best_effort() -> None:
    from app.llm.schemas import CompletionChunk

    client = _fake()
    factory = lambda: CircuitBreaker(failure_threshold=1, recovery_timeout_s=999.0)  # noqa: E731
    client.queue_error(LlmTimeoutError())
    resilient = _resilient([client], max_attempts=1, breaker_factory=factory)
    await resilient.complete(model=_MODEL, messages=_messages())  # abre el unico breaker

    # con el unico breaker OPEN, el stream igual intenta (best-effort).
    client.queue_chunks([CompletionChunk(delta_text="x")])
    chunks = [c async for c in resilient.stream(model=_MODEL, messages=_messages())]
    assert "".join(c.delta_text for c in chunks) == "x"
    assert client.stream_calls


def test_breaker_state_exposed() -> None:
    """Sanidad: el breaker arranca CLOSED para cada client del pool."""
    client = _fake()
    resilient = _resilient([client])
    # El breaker es interno; verificamos via comportamiento publico que
    # arranca permitiendo (CLOSED). Acceso directo solo para sanidad.
    breaker = resilient._breakers[id(client)]
    assert breaker.state is CircuitState.CLOSED
