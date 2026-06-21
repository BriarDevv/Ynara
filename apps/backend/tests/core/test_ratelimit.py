"""Tests del rate-limit / lockout (issue #63), sin Redis (InMemoryTokenStore).

Verifican: el threshold de lockout del login, el reset en login OK, el
aislamiento del bucket por (ip, email) y que la key NUNCA contiene el email
crudo (regla #4). ``get_settings`` se parchea con un Settings determinista
(thresholds chicos) para no depender del entorno.
"""

from __future__ import annotations

import pytest

from app.core import ratelimit
from app.core.config import Settings
from app.core.ratelimit import (
    _chat_counter_key,
    _email_hash,
    _login_counter_key,
    _login_lockout_key,
    _memory_export_counter_key,
    _memory_search_counter_key,
    _refresh_counter_key,
    _sessions_counter_key,
    check_chat_rate_limit,
    check_login_rate_limit,
    check_memory_export_rate_limit,
    check_memory_search_rate_limit,
    check_refresh_rate_limit,
    check_register_rate_limit,
    check_sessions_rate_limit,
    register_login_failure,
    reset_login_rate_limit,
)
from app.core.token_store import InMemoryTokenStore, RedisTokenStore

# asyncio_mode = "auto" (pyproject): los `async def test_*` corren sin marker.

_MAX_ATTEMPTS = 3
_REGISTER_MAX = 2
_REFRESH_MAX = 3
_CHAT_MAX = 2
_EXPORT_MAX = 2
_SEARCH_MAX = 2
_SESSIONS_MAX = 3


def _settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod-min-32b",
        AUTH_LOGIN_MAX_ATTEMPTS=_MAX_ATTEMPTS,
        AUTH_LOGIN_WINDOW_SECONDS=900,
        AUTH_LOGIN_LOCKOUT_SECONDS=900,
        AUTH_REGISTER_MAX_ATTEMPTS=_REGISTER_MAX,
        AUTH_REGISTER_WINDOW_SECONDS=3600,
        AUTH_REFRESH_MAX_ATTEMPTS=_REFRESH_MAX,
        AUTH_REFRESH_WINDOW_SECONDS=900,
        CHAT_MAX_REQUESTS=_CHAT_MAX,
        CHAT_WINDOW_SECONDS=60,
        MEMORY_EXPORT_MAX_REQUESTS=_EXPORT_MAX,
        MEMORY_EXPORT_WINDOW_SECONDS=3600,
        MEMORY_SEARCH_MAX_REQUESTS=_SEARCH_MAX,
        MEMORY_SEARCH_WINDOW_SECONDS=60,
        SESSIONS_MAX_REQUESTS=_SESSIONS_MAX,
        SESSIONS_WINDOW_SECONDS=60,
    )


@pytest.fixture(autouse=True)
def patched_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    s = _settings()
    monkeypatch.setattr("app.core.ratelimit.get_settings", lambda: s)
    return s


# ---------- login lockout ----------


async def test_login_allows_until_threshold() -> None:
    store = InMemoryTokenStore()
    ip, email = "1.2.3.4", "user@example.com"
    # Permitido mientras no se cruce el threshold.
    assert await check_login_rate_limit(store, ip=ip, email=email) is True
    # Registrar (max-1) fallos: sigue permitido.
    for _ in range(_MAX_ATTEMPTS - 1):
        await register_login_failure(store, ip=ip, email=email)
        assert await check_login_rate_limit(store, ip=ip, email=email) is True
    # El fallo que cruza el threshold activa el lockout.
    await register_login_failure(store, ip=ip, email=email)
    assert await check_login_rate_limit(store, ip=ip, email=email) is False


async def test_reset_clears_lockout() -> None:
    store = InMemoryTokenStore()
    ip, email = "1.2.3.4", "user@example.com"
    for _ in range(_MAX_ATTEMPTS):
        await register_login_failure(store, ip=ip, email=email)
    assert await check_login_rate_limit(store, ip=ip, email=email) is False
    # Un login OK limpia contador + lockout: vuelve a permitir.
    await reset_login_rate_limit(store, ip=ip, email=email)
    assert await check_login_rate_limit(store, ip=ip, email=email) is True


async def test_bucket_isolation_by_email() -> None:
    """Dos emails distintos desde la misma IP no comparten contador ni lockout."""
    store = InMemoryTokenStore()
    ip = "1.2.3.4"
    a, b = "alice@example.com", "bob@example.com"
    for _ in range(_MAX_ATTEMPTS):
        await register_login_failure(store, ip=ip, email=a)
    # 'a' está en lockout; 'b' (misma IP) sigue permitido.
    assert await check_login_rate_limit(store, ip=ip, email=a) is False
    assert await check_login_rate_limit(store, ip=ip, email=b) is True


def test_keys_do_not_contain_raw_email() -> None:
    """Las keys usan el sha256 del email, NUNCA el email crudo (regla #4)."""
    email = "secret.pii@example.com"
    counter_key = _login_counter_key("1.2.3.4", email)
    lockout_key = _login_lockout_key("1.2.3.4", email)
    assert email not in counter_key
    assert email not in lockout_key
    # El hash sí aparece (es lo que separa los buckets).
    assert _email_hash(email) in counter_key
    assert _email_hash(email) in lockout_key


def test_email_hash_is_case_insensitive() -> None:
    """A@X.com y a@x.com colapsan al mismo bucket (consistencia con el login)."""
    assert _email_hash("  A@X.com ") == _email_hash("a@x.com")


# ---------- register rate-limit ----------


async def test_register_rate_limit_by_ip() -> None:
    store = InMemoryTokenStore()
    ip = "9.9.9.9"
    # Permitido hasta el max; el (max+1)-ésimo se rechaza.
    for _ in range(_REGISTER_MAX):
        assert await check_register_rate_limit(store, ip=ip) is True
    assert await check_register_rate_limit(store, ip=ip) is False


def test_ratelimit_module_imports_token_store() -> None:
    # Sanity: el módulo expone los helpers públicos esperados.
    assert hasattr(ratelimit, "check_login_rate_limit")
    assert hasattr(ratelimit, "register_login_failure")


# ---------- refresh / chat / export rate-limit (S4) ----------


class _BoomRedisClient:
    """Cliente Redis que lanza en toda op: para ejercitar el fail-open del store."""

    async def eval(self, *a: object, **k: object) -> int:
        raise RuntimeError("redis down")

    async def exists(self, *a: object) -> int:
        raise RuntimeError("redis down")

    async def set(self, *a: object, **k: object) -> None:
        raise RuntimeError("redis down")

    async def delete(self, *a: object) -> None:
        raise RuntimeError("redis down")


async def test_refresh_rate_limit_by_ip_sub() -> None:
    """Permite hasta el max; el (max+1)-ésimo se rechaza. Bucket por (ip, sub)."""
    store = InMemoryTokenStore()
    ip, sub = "1.2.3.4", "user-uuid-1"
    for _ in range(_REFRESH_MAX):
        assert await check_refresh_rate_limit(store, ip=ip, sub=sub) is True
    assert await check_refresh_rate_limit(store, ip=ip, sub=sub) is False


async def test_refresh_bucket_isolation_by_sub() -> None:
    """Dos sub distintos desde la misma IP no comparten contador."""
    store = InMemoryTokenStore()
    ip = "1.2.3.4"
    a, b = "sub-a", "sub-b"
    for _ in range(_REFRESH_MAX):
        await check_refresh_rate_limit(store, ip=ip, sub=a)
    assert await check_refresh_rate_limit(store, ip=ip, sub=a) is False
    assert await check_refresh_rate_limit(store, ip=ip, sub=b) is True


async def test_chat_rate_limit_by_user() -> None:
    """Permite hasta el max; el (max+1)-ésimo se rechaza. Bucket por user_id."""
    store = InMemoryTokenStore()
    user_id = "user-uuid-1"
    for _ in range(_CHAT_MAX):
        assert await check_chat_rate_limit(store, user_id=user_id) is True
    assert await check_chat_rate_limit(store, user_id=user_id) is False


async def test_chat_bucket_isolation_by_user() -> None:
    """Dos user_id distintos no comparten contador (aislamiento por usuario)."""
    store = InMemoryTokenStore()
    a, b = "user-a", "user-b"
    for _ in range(_CHAT_MAX):
        await check_chat_rate_limit(store, user_id=a)
    assert await check_chat_rate_limit(store, user_id=a) is False
    assert await check_chat_rate_limit(store, user_id=b) is True


async def test_memory_export_rate_limit_by_user() -> None:
    """Permite hasta el max; el (max+1)-ésimo se rechaza. Bucket por user_id."""
    store = InMemoryTokenStore()
    user_id = "user-uuid-1"
    for _ in range(_EXPORT_MAX):
        assert await check_memory_export_rate_limit(store, user_id=user_id) is True
    assert await check_memory_export_rate_limit(store, user_id=user_id) is False


async def test_memory_search_rate_limit_by_user() -> None:
    """Permite hasta el max; el (max+1)-ésimo se rechaza. Bucket por user_id."""
    store = InMemoryTokenStore()
    user_id = "user-uuid-1"
    for _ in range(_SEARCH_MAX):
        assert await check_memory_search_rate_limit(store, user_id=user_id) is True
    assert await check_memory_search_rate_limit(store, user_id=user_id) is False


async def test_memory_search_bucket_isolation_by_user() -> None:
    """Dos user_id distintos no comparten contador de búsqueda."""
    store = InMemoryTokenStore()
    a, b = "user-a", "user-b"
    for _ in range(_SEARCH_MAX):
        await check_memory_search_rate_limit(store, user_id=a)
    assert await check_memory_search_rate_limit(store, user_id=a) is False
    assert await check_memory_search_rate_limit(store, user_id=b) is True


# ---------- sessions rate-limit (issue #208) ----------


async def test_sessions_rate_limit_by_user() -> None:
    """Permite hasta el max; el (max+1)-ésimo se rechaza. Bucket por user_id."""
    store = InMemoryTokenStore()
    user_id = "user-uuid-1"
    for _ in range(_SESSIONS_MAX):
        assert await check_sessions_rate_limit(store, user_id=user_id) is True
    assert await check_sessions_rate_limit(store, user_id=user_id) is False


async def test_sessions_bucket_isolation_by_user() -> None:
    """Dos user_id distintos no comparten contador (aislamiento por usuario)."""
    store = InMemoryTokenStore()
    a, b = "user-a", "user-b"
    for _ in range(_SESSIONS_MAX):
        await check_sessions_rate_limit(store, user_id=a)
    # 'a' está bloqueado; 'b' (otro user) sigue permitido.
    assert await check_sessions_rate_limit(store, user_id=a) is False
    assert await check_sessions_rate_limit(store, user_id=b) is True


async def test_fail_open_when_store_degrades() -> None:
    """Si el store degrada (incr_with_ttl => 0), los check_* nuevos PERMITEN (fail-open).

    Un RedisTokenStore que envuelve un cliente que lanza atrapa y devuelve 0 en
    ``incr_with_ttl``; 0 ``<=`` cualquier threshold => True (sin freno, baseline).
    """
    store = RedisTokenStore(_BoomRedisClient())
    # Muchos más golpes que el threshold: igual permite porque el contador es 0.
    for _ in range(_REFRESH_MAX + _CHAT_MAX + _EXPORT_MAX + _SEARCH_MAX + _SESSIONS_MAX + 5):
        assert await check_refresh_rate_limit(store, ip="1.2.3.4", sub="s") is True
        assert await check_chat_rate_limit(store, user_id="u") is True
        assert await check_memory_export_rate_limit(store, user_id="u") is True
        assert await check_memory_search_rate_limit(store, user_id="u") is True
        assert await check_sessions_rate_limit(store, user_id="u") is True


def test_user_id_buckets_keep_raw_uuid() -> None:
    """Las keys de chat/export usan el user_id crudo (UUID opaco, NO PII como el email).

    A diferencia del login (que hashea el email), el user_id/sub es un identificador
    opaco no-personal, así que va crudo en la key — documentado a propósito.
    """
    user_id = "11111111-2222-3333-4444-555555555555"
    assert user_id in _chat_counter_key(user_id)
    assert user_id in _memory_export_counter_key(user_id)
    assert user_id in _memory_search_counter_key(user_id)
    assert user_id in _refresh_counter_key("1.2.3.4", user_id)
    assert user_id in _sessions_counter_key(user_id)
