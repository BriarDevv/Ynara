"""Guard de arranque: impedir que la app boote contra una DB de prod en dev.

Contexto (incidente 2026-05-31): el ``DATABASE_URL`` por default del ``.env``
de desarrollo apunta al **pooler de PRODUCCION** de Supabase
(``...pooler.supabase.com`` / ``*.supabase.co``). Correr la app real en dev
(uvicorn, o un POST contra la app real SIN override de ``get_db``) pega contra
producción — y eso ya creó (y borró) un usuario real en prod.

Este módulo expone dos piezas:

- ``is_prod_db_host(url)`` — helper **puro y testeable**: dado un connection
  string, devuelve ``True`` si el host matchea un patrón de prod conocido
  (Supabase). No tiene efectos secundarios ni lee config global.
- ``guard_against_prod_db_in_dev(...)`` — la lógica del guard. Lo llama el
  lifespan de ``app.main`` como **primera** línea del startup. Levanta
  ``RuntimeError`` con un mensaje accionable (y SIN secretos) si se está
  booteando dev contra una DB de prod por accidente.

Escapes (cualquiera hace que el guard NO se dispare):

1. ``environment == "production"``  → deploy normal, boota contra prod.
2. opt-in explícito ``YNARA_ALLOW_PROD_DB`` ∈ {"1","true","yes"}  → correr
   dev-contra-prod a propósito (corrida consciente).
3. corriendo bajo pytest (``PYTEST_CURRENT_TEST`` en el env o ``pytest`` en
   ``sys.modules``)  → los tests overridean ``get_db``; el guard no debe
   romperlos.

La detección de host se hace por separado (``is_prod_db_host``) para poder
testearla como función pura sin montar la app ni tocar la config global.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from types import ModuleType
from urllib.parse import urlsplit

# Valores que cuentan como opt-in explícito para correr dev-contra-prod.
_ALLOW_PROD_DB_TRUTHY = frozenset({"1", "true", "yes"})

# Nombre de la env var de opt-in (centralizado para reusar en el mensaje).
ALLOW_PROD_DB_ENV = "YNARA_ALLOW_PROD_DB"


def _host_from_netloc(netloc: str) -> str:
    """Fallback manual: host crudo de una netloc ``[user[:pass]@]host[:port]``.

    ``urlsplit(...).hostname`` valida los corchetes de la netloc como literal
    IPv6 y revienta con ``ValueError`` si una credencial trae ``[...]`` —caso
    real: el ``.env.example`` usa ``postgres:[password]@...`` y ``db.[ref]...``
    como placeholders. Acá extraemos el host sin esa validación: cortamos en el
    ÚLTIMO ``@`` (credenciales) y descartamos el ``:port`` final.
    """
    after_creds = netloc.rsplit("@", 1)[-1]  # lo que sigue al último '@'
    # Sacar el puerto: el host es lo previo al último ':' SI lo que sigue es un
    # puerto numérico. (No tocamos hosts con ':' que no sean puerto: en un DSN
    # de Postgres el host no lleva ':' salvo IPv6, fuera de alcance acá.)
    head, sep, tail = after_creds.rpartition(":")
    host = head if (sep and tail.isdigit()) else after_creds
    return host.strip().strip("[]")


def _netloc_from_raw(url: str) -> str:
    """Netloc cruda (``user:pass@host:port``) de un DSN sin validar corchetes.

    ``urlsplit`` valida los corchetes de la netloc y revienta con ``ValueError``
    si una credencial trae ``[...]`` (caso real del ``.env.example``); esto saca
    la netloc del string a mano: lo que va entre ``://`` y el primer ``/``, ``?``
    o ``#``.
    """
    after_scheme = url.split("://", 1)[-1] if "://" in url else url
    # El primer separador de path/query/fragment cierra la netloc.
    for sep in ("/", "?", "#"):
        after_scheme = after_scheme.split(sep, 1)[0]
    return after_scheme


def _host_of(url: str) -> str:
    """Extrae y normaliza el host de un connection string.

    Tolerante a esquemas tipo ``postgresql+asyncpg://``, a credenciales en la
    netloc (``user:pass@host:port``) y a placeholders con corchetes en las
    credenciales (``postgres:[password]@...``), que harían fallar a ``urlsplit``
    entero (no sólo a ``.hostname``). Devuelve el host en minúsculas. String
    vacío si no se puede parsear.
    """
    try:
        host = urlsplit(url).hostname
    except ValueError:
        # netloc con corchetes inválidos (p.ej. password placeholder ``[...]``):
        # urlsplit ni siquiera construye el resultado, así que parseamos el raw.
        host = _host_from_netloc(_netloc_from_raw(url))
    if not host:
        return ""
    return host.strip().lower()


def is_prod_db_host(url: str) -> bool:
    """``True`` si el host del connection string parece una DB de PROD (Supabase).

    Función **pura**: input string → bool. Sin efectos secundarios ni lectura
    de config global. Patrones de prod conocidos (Supabase MVP, ADR-005):

    - ``*.supabase.co``           (conexión directa)
    - ``*.supabase.com``          (poolers regionales: ``...pooler.supabase.com``)
    - host que contiene ``pooler.supabase`` (cinturón y tiradores)

    Localhost / 127.0.0.1 / sockets de la DB de dev local → ``False``.

    TODO (V2 self-hosted): es una allowlist Supabase-only. Si la prod migra
    fuera de Supabase (Postgres gestionado propio / RDS), extender los patrones
    o invertir a denylist de hosts seguros — hoy un host de prod no-Supabase NO
    se detecta y la app bootearía contra él sin avisar.
    """
    host = _host_of(url)
    if not host:
        return False
    return (
        host.endswith(".supabase.co") or host.endswith(".supabase.com") or "pooler.supabase" in host
    )


def _running_under_pytest(
    env: Mapping[str, str],
    modules: Mapping[str, ModuleType],
) -> bool:
    """``True`` si estamos dentro de una corrida de pytest.

    Dos señales independientes: ``PYTEST_CURRENT_TEST`` lo setea pytest por
    test; ``pytest`` en ``sys.modules`` cubre el arranque/colección antes de
    que esa env var exista.
    """
    return "PYTEST_CURRENT_TEST" in env or "pytest" in modules


def _build_guard_message(host: str) -> str:
    """Mensaje accionable y SIN secretos para el ``RuntimeError`` del guard.

    Sólo incluye el *host* (nunca el connection string completo con
    credenciales, regla #2). Explica el qué, el cómo apuntar a dev local, y el
    cómo hacer opt-in si es a propósito.
    """
    return (
        "Guard anti-prod: la app está booteando en modo NO-producción contra una "
        f"base de datos que parece de PRODUCCIÓN (host: {host!r}).\n"
        "Esto fue un incidente real: una corrida en dev contra esta DB creó y "
        "borró un usuario en producción.\n"
        "\n"
        "Qué hacer:\n"
        "  • Para DEV (lo habitual): apuntá DATABASE_URL a tu Postgres LOCAL, por ej.\n"
        "      DATABASE_URL=postgresql://postgres:test@localhost:5433/ynara_dev\n"
        "    (mismo contenedor pgvector de los tests; ver 'Base de datos: dev vs "
        "prod' en apps/backend/README.md).\n"
        f"  • Si querés correr dev CONTRA PROD a propósito: exportá {ALLOW_PROD_DB_ENV}=1\n"
        "    (corrida consciente, bajo tu responsabilidad).\n"
        "  • En el deploy de producción esto no aplica: ENVIRONMENT=production "
        "boota normal."
    )


def guard_against_prod_db_in_dev(
    *,
    environment: str,
    database_url: str,
    env: Mapping[str, str] | None = None,
    modules: Mapping[str, ModuleType] | None = None,
) -> None:
    """Levanta ``RuntimeError`` si se boota dev contra una DB de prod por accidente.

    No-op (return silencioso) en cualquiera de estos casos:

    - ``environment == "production"`` → prod boota normal.
    - opt-in explícito ``YNARA_ALLOW_PROD_DB`` ∈ {"1","true","yes"}.
    - corriendo bajo pytest (los tests overridean ``get_db``).
    - el host de ``database_url`` NO matchea un patrón de prod conocido.

    Args inyectables (``env`` / ``modules``) para testear sin tocar los
    globales del proceso; por default usa ``os.environ`` / ``sys.modules``.
    """
    if env is None:
        env = os.environ
    if modules is None:
        modules = sys.modules

    # 1) Producción: deploy normal, debe bootear contra prod.
    if environment == "production":
        return

    # 2) Opt-in explícito: dev-contra-prod a propósito.
    if env.get(ALLOW_PROD_DB_ENV, "").strip().lower() in _ALLOW_PROD_DB_TRUTHY:
        return

    # 3) Bajo pytest: los E2E overridean get_db; el guard no debe romperlos.
    if _running_under_pytest(env, modules):
        return

    # 4) Llegamos acá => dev real. Si el host es de prod, abortar el arranque.
    if is_prod_db_host(database_url):
        raise RuntimeError(_build_guard_message(_host_of(database_url)))
