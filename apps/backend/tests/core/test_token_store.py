"""Tests del TokenStore: conformidad del Protocol + InMemory blocklist/contadores.

Sin Redis ni red: usan ``InMemoryTokenStore`` (determinista, con ``advance()``
para simular TTL). La conformidad del Protocol se afirma para ambas impls
(espejo del test de ``LLMClient``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.token_store import (
    InMemoryTokenStore,
    RedisTokenStore,
    TokenStore,
)

# asyncio_mode = "auto" (pyproject): los `async def test_*` corren sin marker.


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
