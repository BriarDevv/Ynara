"""Taxonomia de errores de la capa LLM (M1).

Tres familias:

- **Transitorios** (reintentables): timeout, instancia caida, sobrecarga.
- **Permanentes** (no reintentar): request mal formado, contexto excedido,
  modelo no servido.
- **Semanticos**: fallas de parseo / ejecucion de tools y de recuperacion
  de memoria.

Regla #4 (datos del usuario nunca fuera del perimetro): **ninguna
excepcion expone contenido del usuario ni la respuesta del modelo en su
``__str__``**. Los mensajes son etiquetas tecnicas fijas; cualquier detalle
sensible viaja en atributos privados que el logging con scrubbing puede
decidir omitir, nunca en el texto de la excepcion.

``LlmDegradedResponse`` NO es una excepcion: es un helper para construir un
``CompletionResult`` de respuesta degradada (``finish_reason="degraded"``)
cuando toda la cadena de fallback se agoto.
"""

from __future__ import annotations

from app.llm.schemas import CompletionResult


class LlmError(Exception):
    """Raiz de la jerarquia de errores del LLM.

    ``__str__`` devuelve solo una etiqueta tecnica fija; nunca el prompt ni
    la respuesta. Detalles tecnicos no sensibles (status HTTP, nombre del
    modelo) van como argumento opcional ``detail``.
    """

    message: str = "error de inferencia LLM"

    def __init__(self, detail: str | None = None) -> None:
        self._detail = detail
        super().__init__(self.message)

    def __str__(self) -> str:
        if self._detail:
            return f"{self.message}: {self._detail}"
        return self.message


# ---------- Transitorios (reintentables) ----------


class LlmTimeoutError(LlmError):
    """La instancia no respondio dentro del timeout."""

    message = "timeout de inferencia LLM"


class LlmUnavailableError(LlmError):
    """No se pudo conectar a la instancia o devolvio 503."""

    message = "instancia LLM no disponible"


class LlmOverloadedError(LlmError):
    """La instancia rechazo por sobrecarga (HTTP 429)."""

    message = "instancia LLM sobrecargada"


# ---------- Permanentes (no reintentar) ----------


class LlmBadRequestError(LlmError):
    """Request mal formado (HTTP 400/422). No tiene sentido reintentar."""

    message = "request invalido al LLM"


class LlmContextOverflowError(LlmBadRequestError):
    """El prompt + la generacion exceden la ventana de contexto."""

    message = "contexto excedido"


class ModelNotServedError(LlmError):
    """Ninguna instancia del pool sirve el modelo pedido."""

    message = "modelo no servido"


# ---------- Semanticos ----------


class ToolParsingError(LlmError):
    """No se pudo parsear una tool call de la respuesta del modelo.

    No tumba el turno por si misma: el caller decide si degrada o reintenta.
    """

    message = "error parseando tool call"


class ToolExecutionError(LlmError):
    """La ejecucion de una tool fallo.

    Entrada RESERVADA de la taxonomia, todavia NO cableada. El path previsto
    es que ``tool_loop.py`` envuelva los fallos de ejecucion de tool en esta
    excepcion. No es dead-code sino taxonomia forward-looking: ya queda
    cubierta por el ``except LlmError`` de familia que envuelve ``route()``,
    asi que cuando se cablee no requiere tocar el manejo de errores.
    """

    message = "error ejecutando tool"


class MemoryRetrievalError(LlmError):
    """Fallo la recuperacion de contexto de memoria.

    Entrada RESERVADA de la taxonomia, todavia NO cableada. El path previsto
    es que ``memory_engine.py`` envuelva los fallos de retrieval en esta
    excepcion. No es dead-code sino taxonomia forward-looking: ya queda
    cubierta por el ``except LlmError`` de familia que envuelve ``route()``,
    asi que cuando se cablee no requiere tocar el manejo de errores.
    """

    message = "error recuperando memoria"


# ---------- Degradacion (no es excepcion) ----------


def degraded_response(
    *,
    text: str,
    model_name: str,
    latency_ms: float = 0.0,
) -> CompletionResult:
    """Construye un ``CompletionResult`` de respuesta degradada.

    Se usa cuando la cadena de fallback on-prem se agoto y hay que
    devolverle algo coherente al usuario en vez de una excepcion. El
    ``finish_reason`` queda en ``"degraded"`` para que las capas superiores
    lo distingan de una respuesta normal.
    """
    return CompletionResult(
        text=text,
        tool_calls=[],
        finish_reason="degraded",
        prompt_tokens=0,
        completion_tokens=0,
        model_name=model_name,
        latency_ms=latency_ms,
    )
