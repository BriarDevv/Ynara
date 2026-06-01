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
    _email_hash,
    _login_counter_key,
    _login_lockout_key,
    check_login_rate_limit,
    check_register_rate_limit,
    register_login_failure,
    reset_login_rate_limit,
)
from app.core.token_store import InMemoryTokenStore

# asyncio_mode = "auto" (pyproject): los `async def test_*` corren sin marker.

_MAX_ATTEMPTS = 3
_REGISTER_MAX = 2


def _settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-no-usar-en-prod",
        AUTH_LOGIN_MAX_ATTEMPTS=_MAX_ATTEMPTS,
        AUTH_LOGIN_WINDOW_SECONDS=900,
        AUTH_LOGIN_LOCKOUT_SECONDS=900,
        AUTH_REGISTER_MAX_ATTEMPTS=_REGISTER_MAX,
        AUTH_REGISTER_WINDOW_SECONDS=3600,
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
