"""Store de tokens: blocklist de jti + contadores de rate-limit (issue #63).

``TokenStore`` es un ``Protocol`` chico (espejo de ``LLMClient``) con dos
implementaciones:

- ``RedisTokenStore`` (prod): envuelve el ``redis.asyncio.Redis`` singleton de
  ``app.state.redis``. Cada operación es **fail-OPEN**: si Redis cae, las reads
  devuelven el valor seguro (``False`` / "no bloqueado") y las writes son
  best-effort (loguean WARNING y siguen). Justificación: Redis acá es una capa de
  hardening (revocación anticipada + rate-limit), NO la raíz de confianza (esa es
  la firma JWT, que no depende de Redis) ni la fuente de disponibilidad. Una
  caída de Redis vuelve al baseline pre-#63 (JWT stateless puro, sin rate-limit),
  no a una caída total de auth.

- ``InMemoryTokenStore`` (tests): un ``dict`` con expiries simulados, sin red y
  sin ``fakeredis``. Determinista; expone ``advance(seconds)`` para simular TTL
  sin ``sleep`` real.

Regla #4: los logs de fallo de Redis usan SOLO ``type(exc).__name__`` (nunca el
DSN, ``str(exc)`` ni el jti/token crudo), espejo de ``health.check_redis``.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Prefijo de las keys de blocklist. El rate-limit arma sus propias keys (ver
# app/core/ratelimit.py); este prefijo es solo de la blocklist de jti.
_BLOCKLIST_PREFIX = "auth:blocklist:jti:"


@runtime_checkable
class TokenStore(Protocol):
    """Contrato del store de tokens: blocklist + contadores genéricos.

    Las primitivas genéricas (``incr_with_ttl`` / ``set_flag`` / ``has_flag`` /
    ``delete``) las usa el rate-limit; ``revoke`` / ``is_revoked`` son
    convenience de la blocklist (delegan en ``set_flag`` / ``has_flag`` con el
    prefijo ``auth:blocklist:jti:``).
    """

    # --- Blocklist (convenience) ---
    async def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        """Blocklistea un ``jti`` por ``ttl_seconds`` (no-op si ttl <= 0)."""
        ...

    async def is_revoked(self, jti: str) -> bool:
        """``True`` si el ``jti`` está blocklisteado (y no expiró)."""
        ...

    # --- Primitivas genéricas (rate-limit) ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int) -> int:
        """INCR atómico; setea TTL solo si la key nace (primer incr). Devuelve el contador."""
        ...

    async def set_flag(self, key: str, *, ttl_seconds: int) -> None:
        """Setea una flag (valor ``"1"``) con TTL (no-op si ttl <= 0)."""
        ...

    async def has_flag(self, key: str) -> bool:
        """``True`` si la flag existe (y no expiró)."""
        ...

    async def delete(self, *keys: str) -> None:
        """Borra una o más keys (idempotente)."""
        ...


def _blocklist_key(jti: str) -> str:
    return f"{_BLOCKLIST_PREFIX}{jti}"


class RedisTokenStore:
    """Impl de ``TokenStore`` sobre ``redis.asyncio.Redis`` (prod). fail-OPEN.

    No abre ni cierra conexiones: usa el cliente singleton de ``app.state.redis``
    construido en el lifespan. Cada método atrapa CUALQUIER excepción de Redis y
    degrada de forma segura (reads => valor seguro, writes => best-effort),
    logueando solo ``type(exc).__name__`` (regla #4).
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    # --- Blocklist (delegan en las primitivas de flag) ---
    async def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        await self.set_flag(_blocklist_key(jti), ttl_seconds=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return await self.has_flag(_blocklist_key(jti))

    # --- Primitivas genéricas ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int) -> int:
        try:
            count = await self._redis.incr(key)
            # TTL solo en el primer incr (fixed-window): EXPIRE con NX no pisa el
            # TTL si ya existía. (NX en EXPIRE: Redis >= 7.0.)
            if count == 1 and ttl_seconds > 0:
                await self._redis.expire(key, ttl_seconds, nx=True)
            return int(count)
        except Exception as exc:  # fail-open: cualquier fallo de Redis no rompe.
            logger.warning("token_store.incr_with_ttl falló: %s", type(exc).__name__)
            # fail-open: devolver 0 => el rate-limit lo trata como "sin freno"
            # (no cruza el threshold), volviendo al baseline pre-#63.
            return 0

    async def set_flag(self, key: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return  # ya expirado: no escribir basura.
        try:
            await self._redis.set(key, "1", ex=ttl_seconds)
        except Exception as exc:  # best-effort: la write no rompe el endpoint.
            logger.warning("token_store.set_flag falló: %s", type(exc).__name__)

    async def has_flag(self, key: str) -> bool:
        try:
            return bool(await self._redis.exists(key))
        except Exception as exc:  # fail-open: si Redis cae, "no bloqueado".
            logger.warning("token_store.has_flag falló: %s", type(exc).__name__)
            return False

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as exc:  # best-effort.
            logger.warning("token_store.delete falló: %s", type(exc).__name__)


class InMemoryTokenStore:
    """Impl de ``TokenStore`` en memoria (tests). Sin red, sin ``fakeredis``.

    Modela TTL con un epoch de expiración por key. ``advance(seconds)`` simula el
    paso del tiempo (TTL) sin ``sleep`` real, para tests deterministas de
    expiración. ``_now`` es inyectable como hook de clock.
    """

    def __init__(self) -> None:
        self._flags: dict[str, float] = {}  # key -> expiry epoch
        self._counters: dict[str, int] = {}  # key -> contador
        self._counter_expiry: dict[str, float] = {}  # key -> expiry epoch
        self._offset: float = 0.0  # segundos avanzados artificialmente

    def _now(self) -> float:
        return time.monotonic() + self._offset

    def advance(self, seconds: float) -> None:
        """Avanza el reloj simulado ``seconds`` (para tests de expiración de TTL)."""
        self._offset += seconds

    def _purge_expired(self) -> None:
        now = self._now()
        for key in [k for k, exp in self._flags.items() if exp <= now]:
            del self._flags[key]
        for key in [k for k, exp in self._counter_expiry.items() if exp <= now]:
            self._counters.pop(key, None)
            del self._counter_expiry[key]

    # --- Blocklist (delegan en las primitivas de flag) ---
    async def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        await self.set_flag(_blocklist_key(jti), ttl_seconds=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return await self.has_flag(_blocklist_key(jti))

    # --- Primitivas genéricas ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int) -> int:
        self._purge_expired()
        is_new = key not in self._counters
        self._counters[key] = self._counters.get(key, 0) + 1
        if is_new and ttl_seconds > 0:
            self._counter_expiry[key] = self._now() + ttl_seconds
        return self._counters[key]

    async def set_flag(self, key: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self._flags[key] = self._now() + ttl_seconds

    async def has_flag(self, key: str) -> bool:
        self._purge_expired()
        return key in self._flags

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._flags.pop(key, None)
            self._counters.pop(key, None)
            self._counter_expiry.pop(key, None)
