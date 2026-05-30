"""Circuit breaker por instancia LLM (M3).

Implementacion a mano con stdlib (sin libs externas): protege cada
``LLMClient`` del pool de martillar una instancia caida. El ``clock`` es
inyectable para que los tests no usen tiempo real.

Maquina de estados clasica:

- ``CLOSED``   — todo pasa. Al acumular ``failure_threshold`` fallos
  consecutivos, abre.
- ``OPEN``     — bloquea todo hasta que pasen ``recovery_timeout_s``
  desde que abrio; entonces deja pasar una sola prueba (``HALF_OPEN``).
- ``HALF_OPEN`` — deja pasar la prueba. Si tiene exito, vuelve a
  ``CLOSED``; si falla, vuelve a ``OPEN`` (reinicia el temporizador).

El breaker no sabe de ``async``: ``allow()`` / ``record_*`` son sincronos
y el ``ResilientClient`` los orquesta. No es task-safe: bajo requests
concurrentes que comparten el mismo breaker, ``HALF_OPEN`` puede dejar pasar
mas de una prueba. Aceptable en el modelo de uso actual (1-2 procesos, baja
carga); revisitar si hace falta exclusion estricta.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum


class CircuitState(StrEnum):
    """Estados del circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker con clock inyectable para tests deterministas."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configura los umbrales del breaker.

        ``failure_threshold`` es la cantidad de fallos consecutivos en
        ``CLOSED`` que disparan la apertura. ``recovery_timeout_s`` es el
        tiempo que el breaker permanece ``OPEN`` antes de admitir una
        prueba. ``clock`` devuelve un timestamp monotonico en segundos.
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        """Estado actual del breaker (sin side effects)."""
        return self._state

    def allow(self) -> bool:
        """Indica si se puede intentar una request a traves de este breaker.

        En ``OPEN`` chequea si ya paso ``recovery_timeout_s``: si si, pasa a
        ``HALF_OPEN`` y permite una unica prueba; si no, sigue bloqueando.
        """
        if self._state is CircuitState.CLOSED:
            return True
        if self._state is CircuitState.OPEN:
            if self._clock() - self._opened_at >= self._recovery_timeout_s:
                self._state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: la prueba ya esta en curso, se permite.
        return True

    def record_success(self) -> None:
        """Registra un exito: cierra el circuito y resetea el contador."""
        self._state = CircuitState.CLOSED
        self._failures = 0

    def record_failure(self) -> None:
        """Registra un fallo y abre el circuito si corresponde.

        En ``CLOSED`` abre al alcanzar ``failure_threshold``; en
        ``HALF_OPEN`` reabre de inmediato (la prueba fallo).
        """
        if self._state is CircuitState.HALF_OPEN:
            self._open()
            return
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._open()

    def _open(self) -> None:
        """Transiciona a ``OPEN`` y arranca el temporizador de recuperacion."""
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
