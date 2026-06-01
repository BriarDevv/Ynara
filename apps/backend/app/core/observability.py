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
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import get_settings

# Headers que jamás deben viajar a Sentry (auth / sesión).
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_SCRUBBED = "[scrubbed]"

# Guard de idempotencia para ``init_sentry`` (ver item 3 de #66 / docstring).
_initialized = False


def _scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """``before_send`` de Sentry: borra PII del evento antes de transmitirlo.

    Conservador a propósito (regla #4): la política es "ante la duda, fuera".
    Defensa en profundidad: la integración FastAPI/Starlette captura el request
    automáticamente y un ``str(exc)`` de nuestro código podría arrastrar datos de
    usuario, así que limpiamos todos los vectores de PII conocidos antes de
    transmitir. Tolerante a estructura: si una clave no está o viene mal tipada,
    no rompe (``isinstance`` en cada acceso).

    Alcance del scrubbing:

    - ``event['request']``: dropea ``data`` (cuerpo) y ``cookies``; ofusca los
      headers sensibles (``Authorization``, ``Cookie``, etc.) y el ``query_string``.
    - ``event['breadcrumbs']``: ofusca ``message`` y ``data`` de cada breadcrumb
      (pueden traer args/SQL/payloads con PII).
    - ``event['exception']['values'][*]['value']``: ofusca el mensaje de la
      excepción (un ``str(exc)`` nuestro puede traer contenido de usuario),
      preservando ``type`` y ``stacktrace`` para poder diagnosticar.
    - ``event['user']`` / ``event['server_name']`` / ``event['contexts']`` /
      ``event['extra']``: se dropean enteros (IP, email, id, infra on-prem y
      cualquier dato arbitrario que el SDK o nuestro código hayan adjuntado).
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

    # Breadcrumbs: traza de eventos previos al error. ``message`` y ``data``
    # pueden traer args de funciones, SQL o payloads con PII -> los ofuscamos.
    breadcrumbs = event.get("breadcrumbs")
    # Sentry usa {"values": [...]} pero algunos paths pasan la lista directa.
    if isinstance(breadcrumbs, dict):
        crumbs = breadcrumbs.get("values")
    else:
        crumbs = breadcrumbs
    if isinstance(crumbs, list):
        for crumb in crumbs:
            if not isinstance(crumb, dict):
                continue
            if "message" in crumb:
                crumb["message"] = _SCRUBBED
            if "data" in crumb:
                crumb["data"] = _SCRUBBED

    # Excepciones: el mensaje (``value``) de un ``str(exc)`` nuestro puede traer
    # contenido de usuario. Ofuscamos el value pero preservamos type/stacktrace
    # (sin eso no hay forma de diagnosticar el error).
    exception = event.get("exception")
    if isinstance(exception, dict):
        values = exception.get("values")
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict) and "value" in value:
                    value["value"] = _SCRUBBED

    # Contexto de usuario: lo dropeamos entero (IP, email, id no deben salir).
    event.pop("user", None)
    # Hostname del nodo on-prem: dato de infra del cliente, fuera.
    event.pop("server_name", None)
    # Contextos y extras: datos arbitrarios adjuntados por el SDK o nuestro
    # código; ante la duda los dropeamos enteros.
    event.pop("contexts", None)
    event.pop("extra", None)
    return event


def init_sentry() -> None:
    """Inicializa Sentry si hay DSN. No-op si ``SENTRY_DSN`` está vacío.

    Se llama una vez desde ``app.main`` (import-time, antes de crear la app, para
    capturar errores de startup). Sin DSN (default en dev) no hace nada — no se
    manda nada a ningún lado.

    Idempotente (item 3 de #66): ``sentry_sdk.init`` no lo es, y como esto corre
    a import-time de ``app.main``, un reimport del módulo o ``uvicorn --reload``
    re-ejecutaría el ``init`` y duplicaría integraciones. Un flag de módulo hace
    que la segunda llamada sea no-op; la primera se comporta igual que antes.

    El scrubbing de PII (regla #4) aplica a **errores y transacciones**:
    ``before_send`` cubre errores y ``before_send_transaction`` las trazas
    (cuando ``SENTRY_TRACES_SAMPLE_RATE > 0``); sin el segundo, los eventos de
    transacción viajarían sin limpiar. ``transaction_style="endpoint"`` hace que
    el nombre de la transacción sea el patrón de ruta (``/v1/users/{id}``) y no
    la URL resuelta con valores reales.
    """
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=_scrub_event,
        before_send_transaction=_scrub_event,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
    )
    # Recién acá marcamos como inicializado: sin DSN no seteamos el flag, así una
    # llamada no-op (dev sin DSN) no bloquea un init real posterior.
    _initialized = True
