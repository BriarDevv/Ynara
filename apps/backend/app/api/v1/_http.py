"""Helpers HTTP compartidos entre los routers de ``/v1``.

Sede ÚNICA de utilidades de respuesta que varios routers necesitan idénticas, para
no triplicar el mismo helper en ``auth.py`` / ``chat.py`` / ``memory.py`` (deuda
marcada en el review de #156). No importa FastAPI más allá de ``HTTPException`` /
``status`` ni toca dominio: es puro wire.
"""

from __future__ import annotations

from fastapi import HTTPException, status


def too_many_requests(retry_after: int) -> HTTPException:
    """429 uniforme del rate-limit, compartido por los routers de ``/v1``.

    Mismo shape en ``auth.py`` (login/register/refresh), ``chat.py`` (chat) y
    ``memory.py`` (export): un ``detail`` neutro (regla #4: ni PII, ni texto de
    usuario, ni contenido de memoria) + el header ``Retry-After`` con la ventana del
    bucket de CADA call site (cada uno pasa la suya). El ``detail`` uniforme no
    introduce oráculo de enumeración (mismo cuerpo en todos los casos).

    ``retry_after`` (segundos) llena el header ``Retry-After`` para que el cliente
    sepa cuánto esperar antes de reintentar.
    """
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="demasiados intentos, intente mas tarde",
        headers={"Retry-After": str(retry_after)},
    )
