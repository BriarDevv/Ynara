"""Cliente resiliente: retry + circuit breaker + fallback on-prem (M3).

``ResilientClient`` implementa ``LLMClient`` (drop-in para el router) y
envuelve un ``ClientPool``. Politica de resiliencia, toda a mano con
stdlib (regla M3: nada de tenacity/circuitbreaker):

1. Pide al pool los candidatos para el modelo, en orden de preferencia
   (primario primero, secundario on-prem despues).
2. Para cada candidato cuyo breaker ``allow()``:
   - Reintenta ante errores TRANSITORIOS (timeout / no disponible /
     sobrecarga) con backoff exponencial + jitter, hasta ``max_attempts``.
   - Ante un error PERMANENTE (request invalido / modelo no servido)
     re-lanza de inmediato: es bug del request, no falla de infra, y no
     tiene sentido probar el secundario.
   - Si tiene exito, ``record_success()`` y devuelve el resultado.
   - Si agota los reintentos del candidato, ``record_failure()`` y pasa al
     siguiente candidato (fallback on-prem).
3. Si todos los candidatos se agotan (o ninguno tiene el breaker cerrado),
   devuelve ``degraded_response()``. NUNCA propaga una excepcion de infra
   al caller (regla #4 + UX: siempre algo coherente).

Regla #4: el fallback es SIEMPRE on-prem (otra instancia del pool). Cero
APIs externas. ``clock`` y ``sleep`` son inyectables para tests sin tiempo
real.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from app.llm.clients.base import LLMClient
from app.llm.clients.circuit import CircuitBreaker
from app.llm.clients.pool import ClientPool
from app.llm.errors import (
    LlmBadRequestError,
    LlmError,
    ModelNotServedError,
    degraded_response,
)
from app.llm.schemas import (
    ChatMessage,
    CompletionChunk,
    CompletionResult,
    ModelHealth,
    ToolSpec,
)

# Errores PERMANENTES: se re-lanzan sin reintentar ni hacer fallback (bug del
# request, no falla de instancia). Cualquier OTRO ``LlmError`` (timeout,
# instancia caida, sobrecarga, 4xx no mapeado, respuesta malformada, tool parse
# error) es fallback-able: se reintenta y, al agotarse, hace fallback / degrada.
_PERMANENT_ERRORS: tuple[type[LlmError], ...] = (
    LlmBadRequestError,
    ModelNotServedError,
)

_DEFAULT_DEGRADED_TEXT = "Estoy con un problema tecnico, proba en un ratito."


class ResilientClient:
    """Envuelve un ``ClientPool`` con retry, breaker y fallback on-prem."""

    def __init__(
        self,
        pool: ClientPool,
        *,
        max_attempts: int = 3,
        base_backoff_s: float = 0.5,
        max_backoff_s: float = 8.0,
        degraded_text: str = _DEFAULT_DEGRADED_TEXT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        breaker_factory: Callable[[], CircuitBreaker] = CircuitBreaker,
    ) -> None:
        """Configura la politica de resiliencia.

        ``clock`` y ``sleep`` son inyectables para tests deterministas; el
        ``breaker_factory`` construye un ``CircuitBreaker`` por cada cliente
        del pool (uno por instancia, keyed por ``id(client)``).
        """
        self._pool = pool
        self._max_attempts = max_attempts
        self._base_backoff_s = base_backoff_s
        self._max_backoff_s = max_backoff_s
        self._degraded_text = degraded_text
        self._clock = clock
        self._sleep = sleep
        self._breakers: dict[int, CircuitBreaker] = {
            id(client): breaker_factory() for client in pool.clients
        }

    def serves_model(self, model: str) -> bool:
        """``True`` si algun cliente del pool sirve el modelo."""
        return bool(self._pool.candidates(model))

    async def health(self) -> ModelHealth:
        """Salud agregada: sano si al menos un cliente del pool responde.

        Reporta el ``model_name`` del primer cliente sano; si ninguno
        responde, el del primero del pool (o vacio si el pool esta vacio).
        """
        first_name = ""
        for client in self._pool.clients:
            health = await client.health()
            if not first_name:
                first_name = health.model_name
            if health.healthy:
                return ModelHealth(model_name=health.model_name, healthy=True)
        return ModelHealth(model_name=first_name, healthy=False)

    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 30.0,
    ) -> CompletionResult:
        """Completa con retry + fallback on-prem; degrada si todo falla."""
        for client in self._pool.candidates(model):
            breaker = self._breakers[id(client)]
            if not breaker.allow():
                continue
            result = await self._try_candidate(
                client,
                breaker,
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_s=timeout_s,
            )
            if result is not None:
                return result
        return degraded_response(text=self._degraded_text, model_name=model)

    async def _try_candidate(
        self,
        client: LLMClient,
        breaker: CircuitBreaker,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        max_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> CompletionResult | None:
        """Reintenta un candidato; ``None`` si se agota (toca fallback).

        Re-lanza errores permanentes sin tocar el breaker ni el siguiente
        candidato. Ante transitorios reintenta con backoff; al agotarse,
        marca el fallo en el breaker y devuelve ``None``.
        """
        for attempt in range(self._max_attempts):
            try:
                result = await client.complete(
                    model=model,
                    messages=messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_s=timeout_s,
                )
            except _PERMANENT_ERRORS:
                raise
            except LlmError:
                # Transitorio o LlmError de infra no clasificado (4xx no
                # mapeado, respuesta sin choices, tool parse error): reintenta
                # y, al agotar, marca el breaker y hace fallback / degrada.
                if attempt + 1 < self._max_attempts:
                    await self._sleep(self._backoff_delay(attempt))
                continue
            else:
                breaker.record_success()
                return result
        breaker.record_failure()
        return None

    def _backoff_delay(self, attempt: int) -> float:
        """Backoff exponencial cap a ``max_backoff_s`` mas jitter."""
        exponential = self._base_backoff_s * (2**attempt)
        capped = min(exponential, self._max_backoff_s)
        # Jitter para descorrelacionar reintentos de instancias paralelas;
        # no es uso criptografico, asi que ``random`` esta bien (noqa S311).
        jitter = random.uniform(0.0, self._base_backoff_s)  # noqa: S311
        # Cap duro: el jitter no debe empujar el delay por encima del techo.
        return min(capped + jitter, self._max_backoff_s)

    def stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 30.0,
    ) -> AsyncIterator[CompletionChunk]:
        """Streamea desde un candidato sano.

        Limitacion de M3: NO hay fallback mid-stream ni retry una vez que el
        stream arranco. Se elige un candidato con el breaker cerrado y se
        delega; si el primer chunk falla, la excepcion se propaga (el router
        decide como degradar el streaming). El fallback on-prem completo
        solo aplica al modo no-streaming (``complete``).
        """
        return self._stream(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    async def _stream(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        max_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> AsyncIterator[CompletionChunk]:
        client = self._pick_for_stream(model)
        async for chunk in client.stream(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        ):
            yield chunk

    def _pick_for_stream(self, model: str) -> LLMClient:
        """Primer candidato con el breaker cerrado.

        Si TODOS los breakers estan abiertos, cae al primer candidato igual
        (best-effort): streaming no degrada en M3 (ver ``stream``), asi que es
        preferible intentar el stream antes que no devolver nada. Mientras haya
        alguno cerrado, se prefiere ese para no martillar una instancia caida.
        """
        candidates = self._pool.candidates(model)
        if not candidates:
            raise ModelNotServedError(model)
        for client in candidates:
            if self._breakers[id(client)].allow():
                return client
        return candidates[0]
