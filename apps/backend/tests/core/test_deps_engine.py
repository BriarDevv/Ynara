"""Tests de regresion del branching de pooler en ``get_engine`` (deuda D10).

Cubren el switch de ``app.core.deps.get_engine`` segun el puerto del DSN, que es
el mecanismo de compatibilidad con los poolers de Supabase/pgbouncer y de
escalabilidad bajo alta concurrencia:

- Puerto **6543** (transaction pooler): ``poolclass=NullPool`` — el pooling lo
  hace pgbouncer (transaction mode multiplexea miles de clientes sobre pocas
  conexiones server-side), asi que SQLAlchemy NO debe retener conexiones. Con
  NullPool ``pool_size`` se ignora a proposito (no se pasa); el techo de
  concurrencia lo fija pgbouncer (``default_pool_size``/``max_client_conn``), no
  la app.
- Puerto **5432** (session pooler) / conexion directa: ``QueuePool`` con
  ``pool_size=settings.database_pool_size`` — ahi el sizing del lado app si
  importa (techo de Supabase free-tier).
- ``statement_cache_size=0`` se setea SIEMPRE: los prepared statements que
  asyncpg cachea por default rompen contra el transaction pooler (pgbouncer no
  garantiza la misma conexion server entre statements); incondicional para que
  el mismo binario sirva 6543/5432/directo sin ramificar config.
- ``pool_pre_ping=True`` en transaction mode: cada checkout con NullPool+pgbouncer
  es una conexion nueva contra el pooler local, asi que el SELECT 1 del pre-ping
  es de bajo costo y evita servir conexiones muertas tras un restart de
  pgbouncer/Supabase — overhead aceptable, no rompe en transaction mode.

NO tocan DB ni red: ``create_async_engine`` es lazy (no conecta al construir).
Dos estrategias complementarias:

(a) parcheo de ``create_async_engine`` + override de ``get_settings`` para
    assertar con precision los kwargs construidos (patron de ``test_health.py``);
(b) construccion del engine real (lazy) para assertar el tipo de pool efectivo,
    usando DSNs placeholder (usuario/password fake, NUNCA secretos — regla #4),
    al estilo de ``test_db_guard.py``.

``get_engine`` / ``get_sessionmaker`` cachean con ``lru_cache``; el cache es
por-proceso y compartido (``health.py`` tambien lo usa), asi que una fixture
autouse lo limpia antes y despues de cada caso para no contaminar otros tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.pool import NullPool

from app.core import deps
from app.core.config import Settings

# DSNs placeholder: usuario/password fake, host con sufijo de pooler/directo de
# Supabase y puerto explicito. NUNCA credenciales reales (regla #4). No se usa el
# estilo ``[pw]`` con corchetes de ``test_db_guard.py`` porque ``urlsplit().port``
# revienta con ValueError ante el corchete (lo interpreta como literal IPv6).
_URL_TXN_POOLER = "postgresql+asyncpg://postgres:pw@aws-0.pooler.supabase.com:6543/postgres"
_URL_SESSION_POOLER = "postgresql+asyncpg://postgres:pw@aws-0.pooler.supabase.com:5432/postgres"
_URL_DIRECT = "postgresql+asyncpg://postgres:pw@db.ref.supabase.co:5432/postgres"
# DSN SIN puerto explicito: ``urlsplit().port`` devuelve ``None`` (no asume el
# 5432 por default). ``None != 6543`` -> cae al ``else`` -> QueuePool + pool_size.
_URL_NO_PORT = "postgresql+asyncpg://postgres:pw@db.ref.supabase.co/postgres"
# Mismo DSN del transaction pooler pero en formato sync (sin ``+asyncpg``): el
# branch de normalizacion debe reescribirlo a ``postgresql+asyncpg://``.
_URL_SYNC_SCHEME = "postgresql://postgres:pw@aws-0.pooler.supabase.com:6543/postgres"

_POOL_SIZE = 7


def _settings(database_url: str, pool_size: int = _POOL_SIZE) -> Settings:
    """``Settings`` determinista para parchear ``deps.get_settings``.

    ``_env_file=None`` evita leer un ``.env`` real; el resto son placeholders
    minimos para satisfacer los campos requeridos (mismo patron que
    ``test_config``/``test_crypto``).
    """
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL=database_url,
        DATABASE_POOL_SIZE=pool_size,
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="x" * 40,
    )


@pytest.fixture(autouse=True)
def _clear_engine_cache() -> Iterator[None]:
    """Limpia el ``lru_cache`` por-proceso de ``get_engine``/``get_sessionmaker``.

    El cache es compartido (lo consumen ``deps`` y ``health``); limpiarlo antes y
    despues de cada caso evita que un engine de un test se filtre a otro.
    """
    deps.get_engine.cache_clear()
    deps.get_sessionmaker.cache_clear()
    yield
    deps.get_engine.cache_clear()
    deps.get_sessionmaker.cache_clear()


class _RecordingEngine:
    """Sentinel que ``get_engine`` debe retornar tal cual (no conecta nunca)."""


def _patch_create_async_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Parchea ``deps.create_async_engine`` y captura ``(url, kwargs)``.

    Devuelve un dict que se llena en la llamada: ``{"url": ..., "kwargs": ...}``.
    El stub retorna un sentinel para confirmar que ``get_engine`` lo propaga.
    """
    captured: dict[str, Any] = {}

    def _fake(url: str, **kwargs: Any) -> _RecordingEngine:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _RecordingEngine()

    monkeypatch.setattr(deps, "create_async_engine", _fake)
    return captured


# ---------------------------------------------------------------------------
# Estrategia (a): assertar kwargs construidos (mock de create_async_engine)
# ---------------------------------------------------------------------------


def test_transaction_pooler_6543_uses_nullpool_without_pool_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """6543 -> NullPool, statement_cache_size=0, y SIN pool_size."""
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_TXN_POOLER))

    engine = deps.get_engine()

    assert isinstance(engine, _RecordingEngine)  # el sentinel se propaga tal cual
    kwargs = captured["kwargs"]
    assert kwargs["poolclass"] is NullPool
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    # Con NullPool el sizing app-side no aplica: pool_size NO debe pasarse.
    assert "pool_size" not in kwargs


@pytest.mark.parametrize("url", [_URL_SESSION_POOLER, _URL_DIRECT])
def test_session_pooler_and_direct_use_pool_size_without_nullpool(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    """5432 (session pooler) y conexion directa -> pool_size, SIN NullPool."""
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(url))

    deps.get_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_size"] == _POOL_SIZE
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    # En este branch el pooling lo hace SQLAlchemy: NullPool NO debe aparecer.
    assert "poolclass" not in kwargs


def test_url_without_explicit_port_falls_back_to_pool_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSN SIN puerto -> ``urlsplit().port is None`` -> ``else`` (QueuePool + pool_size).

    Edge case del branching: una URL sin ``:puerto`` deja ``port == None``, que NO
    es ``6543``, asi que cae al branch de pooling app-side (comportamiento correcto:
    el transaction pooler SIEMPRE expone el 6543 explicito; sin puerto es conexion
    directa/session). Regresion contra un futuro ``port == 6543`` mal escrito (p.ej.
    ``in (6543, None)``) que prenderia NullPool por error.
    """
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_NO_PORT))

    deps.get_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_size"] == _POOL_SIZE
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    # Sin puerto NO es transaction pooler: NullPool NO debe aparecer.
    assert "poolclass" not in kwargs


@pytest.mark.parametrize("url", [_URL_TXN_POOLER, _URL_SESSION_POOLER, _URL_DIRECT])
def test_invariants_present_in_both_branches(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """``pool_pre_ping=True`` y ``echo=False`` son invariantes de ambos branches."""
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(url))

    deps.get_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["echo"] is False


def test_sync_scheme_is_normalized_to_asyncpg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``postgresql://`` -> ``postgresql+asyncpg://`` en la URL pasada al factory."""
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_SYNC_SCHEME))

    deps.get_engine()

    assert captured["url"] == _URL_TXN_POOLER
    # El puerto sigue detectandose tras normalizar: 6543 -> NullPool.
    assert captured["kwargs"]["poolclass"] is NullPool


def test_asyncpg_scheme_is_not_renormalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un DSN que ya viene ``postgresql+asyncpg://`` NO se reescribe (idempotencia).

    El ``replace(..., 1)`` solo dispara cuando el string ARRANCA con
    ``postgresql://``; un scheme asyncpg no matchea ese prefijo y pasa intacto.
    """
    captured = _patch_create_async_engine(monkeypatch)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_TXN_POOLER))

    deps.get_engine()

    assert captured["url"] == _URL_TXN_POOLER  # sin doble ``+asyncpg``


# ---------------------------------------------------------------------------
# Estrategia (b): engine REAL lazy — assertar el tipo de pool efectivo
# ---------------------------------------------------------------------------
# create_async_engine NO conecta al construir; inspeccionar engine.pool / engine.url
# es seguro en memoria. Disponemos el engine al final para no dejar recursos
# colgando (aunque sin conexiones abiertas, dispose() es barato e idempotente).


@pytest.mark.asyncio
async def test_real_engine_6543_pool_is_nullpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine real para 6543: el pool efectivo es NullPool y el puerto se conserva."""
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_TXN_POOLER))

    engine = deps.get_engine()
    try:
        assert type(engine.pool).__name__ == "NullPool"
        assert engine.url.port == 6543
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_engine_5432_pool_is_not_nullpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine real para 5432: el pool efectivo es QueuePool (no NullPool)."""
    monkeypatch.setattr(deps, "get_settings", lambda: _settings(_URL_DIRECT))

    engine = deps.get_engine()
    try:
        pool_name = type(engine.pool).__name__
        assert pool_name != "NullPool"
        # asyncpg usa el adapter async del QueuePool.
        assert "QueuePool" in pool_name
        assert engine.url.port == 5432
    finally:
        await engine.dispose()
