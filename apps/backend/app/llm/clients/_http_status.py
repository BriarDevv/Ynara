"""Mapeo compartido de status HTTP a la taxonomia ``LlmError``.

``VllmClient`` (chat) tiene su propio ``_raise_for_status`` con deteccion de
overflow de contexto; el embedder y el reranker no necesitan esa rama, asi que
comparten este helper minimo en vez de duplicar el switch en cada cliente.

Regla #4: el detail de la excepcion es una etiqueta fija (``HTTP <status>``),
NUNCA el body crudo (que podria traer texto del usuario).
"""

from __future__ import annotations

import httpx

from app.llm.errors import (
    LlmBadRequestError,
    LlmError,
    LlmOverloadedError,
    LlmUnavailableError,
)


def raise_for_status(response: httpx.Response) -> None:
    """Mapea un status >= 400 a la taxonomia ``LlmError`` (no-op si < 400).

    - 429            -> ``LlmOverloadedError`` (transitorio)
    - 400 / 422      -> ``LlmBadRequestError`` (permanente)
    - 503 / >= 500   -> ``LlmUnavailableError`` (transitorio)
    - otros >= 400   -> ``LlmError`` generico
    """
    status = response.status_code
    if status < 400:
        return
    if status == httpx.codes.TOO_MANY_REQUESTS:
        raise LlmOverloadedError(f"HTTP {status}")
    if status in (httpx.codes.BAD_REQUEST, httpx.codes.UNPROCESSABLE_ENTITY):
        raise LlmBadRequestError(f"HTTP {status}")
    if status >= 500:
        raise LlmUnavailableError(f"HTTP {status}")
    raise LlmError(f"HTTP {status}")
