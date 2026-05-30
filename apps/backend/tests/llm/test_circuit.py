"""Tests del ``CircuitBreaker`` con clock inyectado (M3).

El clock es una lista de un elemento mutable: avanzamos el tiempo seteando
``clock_value[0]`` y le pasamos al breaker un callable que lo lee. Asi los
tests controlan el reloj sin dormir de verdad.
"""

from __future__ import annotations

from app.llm.clients.circuit import CircuitBreaker, CircuitState


class _Clock:
    """Reloj fake controlable: ``now`` avanza a mano."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _breaker(clock: _Clock, *, threshold: int = 3, recovery: float = 30.0) -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=threshold,
        recovery_timeout_s=recovery,
        clock=clock,
    )


def test_starts_closed() -> None:
    breaker = _breaker(_Clock())
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow() is True


def test_opens_on_threshold() -> None:
    breaker = _breaker(_Clock(), threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


def test_open_blocks_before_recovery() -> None:
    clock = _Clock()
    breaker = _breaker(clock, threshold=1, recovery=30.0)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    clock.now = 29.0  # todavia dentro del timeout
    assert breaker.allow() is False
    assert breaker.state is CircuitState.OPEN


def test_open_transitions_to_half_open_after_recovery() -> None:
    clock = _Clock()
    breaker = _breaker(clock, threshold=1, recovery=30.0)
    breaker.record_failure()
    clock.now = 30.0  # exactamente el timeout: permite la prueba
    assert breaker.allow() is True
    assert breaker.state is CircuitState.HALF_OPEN


def test_half_open_success_closes() -> None:
    clock = _Clock()
    breaker = _breaker(clock, threshold=1, recovery=30.0)
    breaker.record_failure()
    clock.now = 30.0
    assert breaker.allow() is True  # -> HALF_OPEN
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow() is True


def test_half_open_failure_reopens() -> None:
    clock = _Clock()
    breaker = _breaker(clock, threshold=1, recovery=30.0)
    breaker.record_failure()
    clock.now = 30.0
    assert breaker.allow() is True  # -> HALF_OPEN
    breaker.record_failure()  # la prueba fallo
    assert breaker.state is CircuitState.OPEN
    # el temporizador se reinicia: bloquea de nuevo hasta el proximo timeout.
    assert breaker.allow() is False
    clock.now = 60.0
    assert breaker.allow() is True


def test_success_resets_failure_count() -> None:
    breaker = _breaker(_Clock(), threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()  # resetea el contador
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED  # solo 2 fallos tras el reset
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
