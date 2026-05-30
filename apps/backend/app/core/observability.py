"""Observabilidad: inicialización de Sentry con scrubbing de PII (regla #4).

Ynara es privacy-first y on-prem: **ningún dato de usuario puede salir hacia un
servicio externo de error tracking** (regla #4 de AGENTS.md). Sentry se inicializa
solo si hay ``SENTRY_DSN`` y SIEMPRE con un ``before_send`` que limpia el evento
de cuerpo de request, cookies, headers de auth, query string y contexto de
usuario antes de que salga del proceso. Además ``send_default_pii=False`` para
que el SDK no adjunte IP/cookies/usuario por su cuenta.

El scrubber es defensa en profundidad: aunque nuestro código no loguee PII, la
integración FastAPI de Sentry captura el request automáticamente. Lo limpiamos
antes de transmitir.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk

from app.core.config import get_settings

# Headers que jamás deben viajar a Sentry (auth / sesión).
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_SCRUBBED = "[scrubbed]"


def _scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """``before_send`` de Sentry: borra PII del evento antes de transmitirlo.

    Conservador a propósito (regla #4): elimina el cuerpo del request, las
    cookies y el contexto de usuario; ofusca headers sensibles y el query
    string. Tolerante a estructura: si una clave no está, no rompe.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)  # cuerpo del request (puede traer PII)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in _SENSITIVE_HEADERS:
                    headers[name] = _SCRUBBED
        if request.get("query_string"):
            request["query_string"] = _SCRUBBED

    # Contexto de usuario: lo dropeamos entero (IP, email, id no deben salir).
    event.pop("user", None)
    return event


def init_sentry() -> None:
    """Inicializa Sentry si hay DSN. No-op si ``SENTRY_DSN`` está vacío.

    Idempotente a nivel boot: se llama una vez desde ``app.main``. Sin DSN
    (default en dev) no hace nada — no se manda nada a ningún lado.
    """
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=_scrub_event,
    )
