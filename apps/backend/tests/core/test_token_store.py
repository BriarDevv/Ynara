"""Tests del TokenStore: conformidad del Protocol + InMemory blocklist/contadores.

Sin Redis ni red: usan ``InMemoryTokenStore`` (determinista, con ``advance()``
para simular TTL). La conformidad del Protocol se afirma para ambas impls
(espejo del test de ``LLMClient``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import app.core.token_store as token_store_module
from app.core.token_store import (
    InMemoryTokenStore,
    RedisTokenStore,
    TokenStore,
)

# asyncio_mode = "auto" (pyproject): los `async def test_*` corren sin marker.


class _BoomRedisClient:
    """Cliente Redis que explota en toda llamada: ejercita el camino fail-open.

    Espejo del ``_BoomRedisClient`` de ``tests/api/test_auth.py`` (mismo patrón).
    Cada método del ``RedisTokenStore`` debe atrapar la excepción y degradar seguro
    (reads => valor seguro, writes => best-effort), sin propagar.
    """

    async def set(self, *a: object, **k: object) -> None:
        raise RuntimeError("redis down")

    async def get(self, *a: object) -> object:
        raise RuntimeError("redis down")

    async def exists(self, *a: object) -> int:
        raise RuntimeError("redis down")

    async def mget(self, *a: object) -> list[object]:
        raise RuntimeError("redis down")

    async def eval(self, *a: object, **k: object) -> int:
        raise RuntimeError("redis down")

    async def delete(self, *a: object) -> None:
        raise RuntimeError("redis down")


# ---------- conformidad del Protocol ----------


def test_inmemory_conforms_protocol() -> None:
    assert isinstance(InMemoryTokenStore(), TokenStore)


def test_redis_store_conforms_protocol() -> None:
    # No conecta: solo verifica que la clase satisface el Protocol estructural.
    assert isinstance(RedisTokenStore(MagicMock()), TokenStore)


# ---------- blocklist ----------


async def test_revoke_then_is_revoked() -> None:
    store = InMemoryTokenStore()
    await store.revoke("jti-1", ttl_seconds=60)
    assert await store.is_revoked("jti-1") is True
    # Un jti distinto no está bloqueado.
    assert await store.is_revoked("jti-otro") is False


async def test_revoke_zero_ttl_is_noop() -> None:
    store = InMemoryTokenStore()
    await store.revoke("jti-vencido", ttl_seconds=0)
    assert await store.is_revoked("jti-vencido") is False


async def test_blocklist_expires_after_ttl() -> None:
    store = InMemoryTokenStore()
    await store.revoke("jti-1", ttl_seconds=10)
    assert await store.is_revoked("jti-1") is True
    store.advance(11)  # pasa el TTL
    assert await store.is_revoked("jti-1") is False


# ---------- revoke_if_absent (claim atómico, item 3 de #142) ----------


async def test_revoke_if_absent_inmemory_first_wins_then_loses() -> None:
    """Primera vez gana el claim (True); la segunda lo encuentra ya revocado (False)."""
    store = InMemoryTokenStore()
    assert await store.revoke_if_absent("jti-1", ttl_seconds=60) is True
    # Quedó blocklisteado.
    assert await store.is_revoked("jti-1") is True
    # Segundo intento sobre el MISMO jti: ya estaba -> pierde la carrera.
    assert await store.revoke_if_absent("jti-1", ttl_seconds=60) is False


async def test_revoke_if_absent_inmemory_zero_ttl_no_escribe() -> None:
    """ttl <= 0 (token ya expirado): True sin escribir (no se blocklistea nada)."""
    store = InMemoryTokenStore()
    assert await store.revoke_if_absent("jti-vencido", ttl_seconds=0) is True
    assert await store.is_revoked("jti-vencido") is False


async def test_revoke_if_absent_redis_first_wins_then_loses() -> None:
    """RedisTokenStore: SET NX EX -> True si lo seteó este caller, False si ya estaba."""

    class _NxRedis:
        """Modela SET NX: devuelve True solo si la key no existía."""

        def __init__(self) -> None:
            self._keys: set[str] = set()

        async def set(self, key: str, _v: str, *, nx: bool = False, ex: int = 0) -> bool | None:
            if nx and key in self._keys:
                return None  # ya existía -> NX no setea.
            self._keys.add(key)
            return True

    store = RedisTokenStore(_NxRedis())
    assert await store.revoke_if_absent("jti-1", ttl_seconds=60) is True
    # Segundo intento: la key ya existe -> NX devuelve None -> False.
    assert await store.revoke_if_absent("jti-1", ttl_seconds=60) is False


async def test_revoke_if_absent_redis_fail_open_devuelve_true() -> None:
    """fail-open: ante un Redis que explota, revoke_if_absent permite la rotación (True)."""
    store = RedisTokenStore(_BoomRedisClient())
    assert await store.revoke_if_absent("jti-1", ttl_seconds=60) is True


# ---------- familia (sid) + grace marker (item 1 de #142) ----------


async def test_revoke_family_then_is_family_revoked() -> None:
    """revoke_family(sid) bloquea esa familia; otra familia sigue libre."""
    store = InMemoryTokenStore()
    assert await store.is_family_revoked("S") is False
    await store.revoke_family("S", ttl_seconds=60)
    assert await store.is_family_revoked("S") is True
    # Otra familia (otro sid) no se ve afectada (aislamiento por sesión).
    assert await store.is_family_revoked("OTRA") is False


async def test_family_revoked_expires_after_ttl() -> None:
    """La revocación de familia self-expira al pasar el TTL."""
    store = InMemoryTokenStore()
    await store.revoke_family("S", ttl_seconds=10)
    assert await store.is_family_revoked("S") is True
    store.advance(11)
    assert await store.is_family_revoked("S") is False


async def test_grace_marker_roundtrip() -> None:
    """set_grace_marker guarda el successor; get_grace_marker lo devuelve."""
    store = InMemoryTokenStore()
    assert await store.get_grace_marker("old") is None
    await store.set_grace_marker("old", "successor-jti", ttl_seconds=30)
    assert await store.get_grace_marker("old") == "successor-jti"
    # Un jti distinto no tiene grace marker.
    assert await store.get_grace_marker("otro") is None


async def test_grace_marker_expires() -> None:
    """El grace marker self-expira al pasar la ventana."""
    store = InMemoryTokenStore()
    await store.set_grace_marker("old", "succ", ttl_seconds=30)
    assert await store.get_grace_marker("old") == "succ"
    store.advance(31)  # pasa el grace
    assert await store.get_grace_marker("old") is None


async def test_grace_marker_zero_ttl_noop() -> None:
    """ttl <= 0: no se escribe el grace marker (no-op)."""
    store = InMemoryTokenStore()
    await store.set_grace_marker("old", "succ", ttl_seconds=0)
    assert await store.get_grace_marker("old") is None


async def test_auth_status_combines_jti_and_family() -> None:
    """auth_status devuelve (jti_revocado, family_revocada) para cada combinación."""
    store = InMemoryTokenStore()
    # Ninguno revocado.
    assert await store.auth_status("jti-A", "sid-A") == (False, False)
    # Solo jti.
    await store.revoke("jti-A", ttl_seconds=60)
    assert await store.auth_status("jti-A", "sid-A") == (True, False)
    # jti + familia.
    await store.revoke_family("sid-A", ttl_seconds=60)
    assert await store.auth_status("jti-A", "sid-A") == (True, True)
    # Solo familia (otro jti vivo).
    assert await store.auth_status("jti-vivo", "sid-A") == (False, True)
    # Compat: ambos None -> (False, False) (token pre-#63 puro).
    assert await store.auth_status(None, None) == (False, False)
    # Solo jti presente (sin sid) -> family slot False.
    assert await store.auth_status("jti-A", None) == (True, False)
    # Solo sid presente (sin jti) -> jti slot False.
    assert await store.auth_status(None, "sid-A") == (False, True)


async def test_auth_status_redis_mget_single_key() -> None:
    """RedisTokenStore.auth_status mapea bien cuando solo uno de jti/sid está presente.

    MGET con una sola key devuelve una lista de longitud 1: el código no debe
    asumir un índice fijo (jti en 0, sid en 1) sino trackear qué slot es cuál.
    """

    class _MgetRedis:
        def __init__(self, revoked: set[str]) -> None:
            self._revoked = revoked

        async def mget(self, keys: list[str]) -> list[object]:
            return ["1" if k in self._revoked else None for k in keys]

    # Solo la family key está revocada; pasamos solo sid (1 key en el MGET).
    family_key = "auth:revoked_family:sid-A"
    store = RedisTokenStore(_MgetRedis({family_key}))
    assert await store.auth_status(None, "sid-A") == (False, True)
    # Solo jti presente, no revocado.
    assert await store.auth_status("jti-vivo", None) == (False, False)
    # Ambos presentes: jti vivo, familia revocada.
    assert await store.auth_status("jti-vivo", "sid-A") == (False, True)


async def test_auth_status_redis_fail_open() -> None:
    """fail-open: si el MGET explota, auth_status devuelve (False, False)."""
    store = RedisTokenStore(_BoomRedisClient())
    assert await store.auth_status("jti", "sid") == (False, False)


async def test_grace_marker_redis_fail_open_devuelve_none() -> None:
    """fail-open: si el GET del grace explota, get_grace_marker devuelve None."""
    store = RedisTokenStore(_BoomRedisClient())
    assert await store.get_grace_marker("old") is None


async def test_grace_marker_redis_decodes_bytes() -> None:
    """get_grace_marker decodifica bytes (redis-py sin decode_responses)."""

    class _BytesRedis:
        async def get(self, _key: str) -> bytes:
            return b"successor-jti"

    store = RedisTokenStore(_BytesRedis())
    assert await store.get_grace_marker("old") == "successor-jti"


# ---------- contadores (rate-limit) ----------


async def test_incr_with_ttl_increments() -> None:
    store = InMemoryTokenStore()
    assert await store.incr_with_ttl("k", ttl_seconds=60) == 1
    assert await store.incr_with_ttl("k", ttl_seconds=60) == 2
    assert await store.incr_with_ttl("k", ttl_seconds=60) == 3


async def test_incr_ttl_set_only_on_first() -> None:
    """El TTL se fija solo en el primer incr (fixed-window): el contador expira junto."""
    store = InMemoryTokenStore()
    await store.incr_with_ttl("k", ttl_seconds=10)
    store.advance(5)
    # El segundo incr NO reinicia la ventana.
    await store.incr_with_ttl("k", ttl_seconds=10)
    store.advance(6)  # 11s desde el primer incr => ventana vencida
    assert await store.incr_with_ttl("k", ttl_seconds=10) == 1  # contador reseteado


async def test_set_has_delete_flag_roundtrip() -> None:
    store = InMemoryTokenStore()
    assert await store.has_flag("f") is False
    await store.set_flag("f", ttl_seconds=60)
    assert await store.has_flag("f") is True
    await store.delete("f")
    assert await store.has_flag("f") is False


async def test_flag_expires_after_ttl() -> None:
    store = InMemoryTokenStore()
    await store.set_flag("f", ttl_seconds=10)
    assert await store.has_flag("f") is True
    store.advance(11)
    assert await store.has_flag("f") is False


# ---------- incr_with_ttl atómico (Lua, item 4 de #142) ----------


async def test_redis_incr_with_ttl_key_nace_con_ttl() -> None:
    """Invariante: tras el primer incr la key del contador SIEMPRE tiene TTL.

    El fix (item 4) hace INCR+EXPIRE en un script Lua atómico: la key no puede
    quedar huérfana (sin TTL) ni siquiera si el proceso muere entre medio. Acá
    modelamos el contrato del script: el primer incr (c == 1) corre EXPIRE; los
    siguientes NO (fixed-window, no se reinicia la ventana).
    """

    class _LuaRedis:
        """Modela el script INCR+EXPIRE atómico: EXPIRE solo en el primer incr."""

        def __init__(self) -> None:
            self.counters: dict[str, int] = {}
            self.ttls: dict[str, int] = {}

        async def eval(self, _script: str, _numkeys: int, key: str, ttl: int) -> int:
            self.counters[key] = self.counters.get(key, 0) + 1
            if self.counters[key] == 1:
                self.ttls[key] = int(ttl)
            return self.counters[key]

    redis = _LuaRedis()
    store = RedisTokenStore(redis)
    assert await store.incr_with_ttl("k", ttl_seconds=900) == 1
    # Tras el primer incr, la key nació con TTL (invariante: nunca huérfana).
    assert redis.ttls["k"] == 900
    # Segundo incr: NO reinicia el TTL (fixed-window preservado).
    assert await store.incr_with_ttl("k", ttl_seconds=900) == 2
    assert redis.ttls["k"] == 900


async def test_redis_incr_with_ttl_fail_open_devuelve_cero() -> None:
    """fail-open: si el eval del script explota, incr_with_ttl devuelve 0 (sin freno)."""
    store = RedisTokenStore(_BoomRedisClient())
    assert await store.incr_with_ttl("k", ttl_seconds=900) == 0


# ---------- alerting del fail-open (Sentry rate-limitado, item 2 de #142) ----------


@pytest.fixture(autouse=True)
def _reset_degraded_gate() -> None:
    """Limpia el gate de rate-limit del alerting entre tests (estado de módulo)."""
    token_store_module._last_degraded_alert.clear()


async def test_fail_open_dispara_capture_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """El camino boom emite un sentry_sdk.capture_message (alerting del fail-open)."""
    calls: list[tuple[str, str]] = []

    def _fake_capture(message: str, *, level: str = "info", **_k: object) -> None:
        calls.append((message, level))

    monkeypatch.setattr(token_store_module.sentry_sdk, "capture_message", _fake_capture)

    store = RedisTokenStore(_BoomRedisClient())
    secret_key = "auth:blocklist:jti:SECRET-JTI-MARKER"
    assert await store.has_flag(secret_key) is False  # fail-open, no rompe.
    assert len(calls) == 1
    message, level = calls[0]
    assert level == "warning"
    assert "has_flag" in message
    # Regla #4: solo op + type(exc).__name__, nunca jti/key/DSN/str(exc).
    assert "RuntimeError" in message
    assert "redis down" not in message
    assert "SECRET-JTI-MARKER" not in message


async def test_fail_open_alert_rate_limitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos fallos seguidos de la MISMA op dentro de la ventana -> un solo capture_message."""
    calls: list[str] = []

    def _fake_capture(message: str, *, level: str = "info", **_k: object) -> None:
        calls.append(message)

    monkeypatch.setattr(token_store_module.sentry_sdk, "capture_message", _fake_capture)

    store = RedisTokenStore(_BoomRedisClient())
    # Dos reads consecutivas de la misma op: el gate rate-limita el segundo alert.
    assert await store.has_flag("a") is False
    assert await store.has_flag("b") is False
    assert len(calls) == 1  # el segundo cae dentro de la ventana de ~60s.


async def test_fail_open_alert_por_op_independiente(monkeypatch: pytest.MonkeyPatch) -> None:
    """El rate-limit es POR nombre de op: ops distintas disparan alerts distintos."""
    ops: list[str] = []

    def _fake_capture(message: str, *, level: str = "info", **_k: object) -> None:
        ops.append(message)

    monkeypatch.setattr(token_store_module.sentry_sdk, "capture_message", _fake_capture)

    store = RedisTokenStore(_BoomRedisClient())
    assert await store.has_flag("x") is False  # op has_flag
    await store.delete("y")  # op delete (distinta)
    # Dos ops distintas -> dos alerts (el gate es per-op).
    assert len(ops) == 2
    assert any("has_flag" in m for m in ops)
    assert any("delete" in m for m in ops)
