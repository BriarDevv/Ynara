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

import sentry_sdk

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Prefijo de las keys de blocklist. El rate-limit arma sus propias keys (ver
# app/core/ratelimit.py); este prefijo es solo de la blocklist de jti.
_BLOCKLIST_PREFIX = "auth:blocklist:jti:"

# Revocacion a nivel familia (sid), item 1 de #142: mata el access + todos los
# refresh de una sesion de una. TTL = vida del refresh (la familia sobrevive a
# cualquier jti individual).
_FAMILY_REVOKED_PREFIX = "auth:revoked_family:"
# Marker de gracia post-rotacion (item 1 de #142): vive corto (grace seconds).
# Su VALOR es el jti del refresh sucesor, para que un retry benigno dentro de la
# ventana sea idempotente (re-rotar en vez de 401/family-revoke). NO es un token
# crudo (es un jti, un marker), asi que guardar el valor respeta la regla #4.
_ROTATED_GRACE_PREFIX = "auth:rotated_grace:"

# INCR + EXPIRE atómico para el contador de rate-limit (fixed-window). El EXPIRE
# corre SOLO en el primer incr (``c == 1``), así la ventana no se reinicia en cada
# golpe. Un INCR seguido de un EXPIRE por separado NO es atómico: si el proceso
# muere o el EXPIRE falla en el medio, la key queda huérfana (sin TTL) y el
# contador no expira nunca. El script lo hace en un único round-trip indivisible
# y NO usa ``EXPIRE NX`` (que exige Redis SERVER >= 7); funciona desde Redis 2.6.
_INCR_WITH_TTL_LUA = (
    'local c = redis.call("INCRBY", KEYS[1], ARGV[2])\n'
    'if c == tonumber(ARGV[2]) then redis.call("EXPIRE", KEYS[1], ARGV[1]) end\n'
    "return c"
)

# Rate-limit del alerting de fail-open (item 2 de #142): a lo sumo 1
# ``capture_message`` cada ~60s POR nombre de op. El gate vive en memoria del
# proceso (``time.monotonic()``) y NO puede apoyarse en Redis: Redis es justo lo
# que está caído cuando este alerting dispara.
_DEGRADED_ALERT_WINDOW_SECONDS = 60.0
# op-name -> último monotonic en que se emitió un capture_message para esa op.
# El estado es POR-PROCESO (dict en memoria del worker), intencional bajo el
# despliegue single-worker actual: 1 alert por op por ventana. Con N workers el
# gate NO se comparte (no puede apoyarse en Redis, que es lo que está caído), así
# que se esperan hasta N alerts por ventana (uno por proceso). Aceptable: el
# objetivo es acotar el ruido, no garantizar exactamente-uno global.
_last_degraded_alert: dict[str, float] = {}


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

    async def revoke_if_absent(self, jti: str, *, ttl_seconds: int) -> bool:
        """Claim atómico: blocklistea el ``jti`` SOLO si no estaba ya revocado.

        Devuelve ``True`` si ESTE caller ganó la carrera (lo seteó él), ``False``
        si el ``jti`` ya estaba blocklisteado. Cierra el TOCTOU del refresh
        (``is_revoked`` + ``revoke`` por separado dejaban una ventana donde dos
        rotaciones concurrentes del mismo refresh pasaban ambas). ``ttl_seconds <=
        0`` (token ya expirado) -> ``True`` sin escribir.
        """
        ...

    async def is_revoked(self, jti: str) -> bool:
        """``True`` si el ``jti`` está blocklisteado (y no expiró)."""
        ...

    # --- Familia (sid) + grace marker (item 1 de #142) ---
    async def revoke_family(self, sid: str, *, ttl_seconds: int) -> None:
        """Revoca la familia entera (``sid``): mata access + todos los refresh de la sesion."""
        ...

    async def is_family_revoked(self, sid: str) -> bool:
        """``True`` si la familia (``sid``) está revocada (y no expiró)."""
        ...

    async def set_grace_marker(self, old_jti: str, successor_jti: str, *, ttl_seconds: int) -> None:
        """Marca ``old_jti`` como recién-rotado, guardando el jti del sucesor.

        El sucesor habilita la idempotencia del retry benigno (un reenvío del
        mismo refresh dentro de la ventana de gracia se trata como reintento, no
        como reuse). No-op si ttl <= 0.
        """
        ...

    async def get_grace_marker(self, old_jti: str) -> str | None:
        """Devuelve el ``successor_jti`` si ``old_jti`` está dentro del grace; si no, ``None``."""
        ...

    async def auth_status(self, jti: str | None, sid: str | None) -> tuple[bool, bool]:
        """Devuelve ``(jti_revocado, family_revocada)`` en UN solo round-trip a Redis.

        Reemplaza el ``is_revoked(jti)`` + ``is_family_revoked(sid)`` por separado
        en el hot-path de ``get_current_claims`` (cada request autenticado). Si
        ``jti``/``sid`` es ``None`` (token viejo sin ese claim), ese componente
        devuelve ``False`` (skip). fail-OPEN: si Redis cae, ``(False, False)`` -> el
        token se acepta hasta su ``exp``.
        """
        ...

    # --- Primitivas genéricas (rate-limit) ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        """INCRBY atómico; setea TTL solo si la key nace. Devuelve el contador.

        ``amount`` (default 1) permite cargar varios "puntos" de presupuesto en una sola
        operación (p.ej. la amplificación de escrituras de un turno de chat con tools). El
        EXPIRE se setea SOLO cuando la key nace (el contador devuelto == ``amount``), igual
        que con el incr de a 1: la ventana fija no se renueva en cada carga.
        """
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


def _family_key(sid: str) -> str:
    return f"{_FAMILY_REVOKED_PREFIX}{sid}"


def _grace_key(jti: str) -> str:
    return f"{_ROTATED_GRACE_PREFIX}{jti}"


def _report_degraded(op: str, exc: Exception) -> None:
    """Reporta un fail-open del ``RedisTokenStore``: WARNING + Sentry rate-limitado.

    Centraliza lo que cada ``except`` del ``RedisTokenStore`` hace al degradar
    (item 2 de #142): el ``logger.warning`` de siempre MÁS un
    ``sentry_sdk.capture_message`` para tener alerting del fail-open (un Redis
    caído debe ser visible, no silencioso). El Sentry está rate-limitado a 1
    evento cada ``_DEGRADED_ALERT_WINDOW_SECONDS`` POR nombre de op para no
    inundar el error tracking mientras Redis está caído; el gate usa
    ``time.monotonic()`` (NO Redis: es justo lo que falló).

    Regla #4: el mensaje contiene SOLO el nombre de la op + ``type(exc).__name__``
    — NUNCA el jti/key/DSN ni ``str(exc)``. Si no hay ``SENTRY_DSN``,
    ``capture_message`` es un no-op seguro (Sentry sin init no manda nada).
    """
    logger.warning("token_store.%s falló: %s", op, type(exc).__name__)
    now = time.monotonic()
    last = _last_degraded_alert.get(op)
    if last is not None and now - last < _DEGRADED_ALERT_WINDOW_SECONDS:
        return  # dentro de la ventana: no re-disparar el alert para esta op.
    _last_degraded_alert[op] = now
    sentry_sdk.capture_message(
        f"token_store.{op} degradado (fail-open): {type(exc).__name__}",
        level="warning",
    )


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

    async def revoke_if_absent(self, jti: str, *, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            # Token ya expirado: no hace falta blocklistear (la firma ya lo
            # rechaza). Devolvemos True para que el caller siga la rotación.
            return True
        try:
            # SET NX EX en un único round-trip (Redis 2.6+): setea SOLO si la key
            # no existía. ``res is True`` => ganamos la carrera (lo seteamos);
            # ``None`` => ya estaba revocado (otro lo seteó antes). Atómico, cierra
            # el TOCTOU del refresh.
            res = await self._redis.set(_blocklist_key(jti), "1", nx=True, ex=ttl_seconds)
            return res is True
        except Exception as exc:  # fail-open: Redis caído permite la rotación.
            _report_degraded("revoke_if_absent", exc)
            # fail-open: True => permitir la rotación (baseline pre-#63, sin
            # detección de reuse). Mejor degradar a "rota igual" que romper auth.
            return True

    async def is_revoked(self, jti: str) -> bool:
        return await self.has_flag(_blocklist_key(jti))

    # --- Familia (sid) + grace marker (item 1 de #142) ---
    async def revoke_family(self, sid: str, *, ttl_seconds: int) -> None:
        await self.set_flag(_family_key(sid), ttl_seconds=ttl_seconds)

    async def is_family_revoked(self, sid: str) -> bool:
        return await self.has_flag(_family_key(sid))

    async def set_grace_marker(self, old_jti: str, successor_jti: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return  # ya expirado: no escribir basura.
        try:
            # Guarda el successor_jti como VALOR (no "1"): el retry benigno lo lee
            # para decidir idempotencia. best-effort (mismo patron que set_flag).
            await self._redis.set(_grace_key(old_jti), successor_jti, ex=ttl_seconds)
        except Exception as exc:  # best-effort: la write no rompe el endpoint.
            _report_degraded("set_grace_marker", exc)

    async def get_grace_marker(self, old_jti: str) -> str | None:
        try:
            val = await self._redis.get(_grace_key(old_jti))
        except Exception as exc:  # fail-open: si Redis cae, "no hay grace".
            _report_degraded("get_grace_marker", exc)
            return None
        if val is None:
            return None
        # redis-py puede devolver bytes (decode_responses=False) o str.
        return val.decode() if isinstance(val, bytes) else str(val)

    async def auth_status(self, jti: str | None, sid: str | None) -> tuple[bool, bool]:
        # Un solo MGET de las keys presentes (1 RTT en vez de 2). Trackeamos que
        # slot de la respuesta corresponde a jti y cual a sid (cuando solo uno
        # esta presente, MGET devuelve una lista de longitud 1).
        keys: list[str] = []
        jti_idx: int | None = None
        sid_idx: int | None = None
        if jti is not None:
            jti_idx = len(keys)
            keys.append(_blocklist_key(jti))
        if sid is not None:
            sid_idx = len(keys)
            keys.append(_family_key(sid))
        if not keys:
            return (False, False)
        try:
            vals = await self._redis.mget(keys)  # 1 RTT
        except Exception as exc:  # fail-open: Redis caido -> nada revocado.
            _report_degraded("auth_status", exc)
            return (False, False)
        jti_revoked = jti_idx is not None and vals[jti_idx] is not None
        family_revoked = sid_idx is not None and vals[sid_idx] is not None
        return (jti_revoked, family_revoked)

    # --- Primitivas genéricas ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        try:
            # INCRBY + EXPIRE atómico vía Lua (ver _INCR_WITH_TTL_LUA): el EXPIRE
            # corre solo cuando la key nace (contador == amount, fixed-window) y la key
            # SIEMPRE nace con TTL (no queda huérfana si el proceso muere entre INCRBY y
            # EXPIRE). ``amount`` carga varios puntos de presupuesto de una.
            count = await self._redis.eval(_INCR_WITH_TTL_LUA, 1, key, ttl_seconds, amount)
            return int(count)
        except Exception as exc:  # fail-open: cualquier fallo de Redis no rompe.
            _report_degraded("incr_with_ttl", exc)
            # fail-open: devolver 0 => el rate-limit lo trata como "sin freno"
            # (no cruza el threshold), volviendo al baseline pre-#63.
            return 0

    async def set_flag(self, key: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return  # ya expirado: no escribir basura.
        try:
            await self._redis.set(key, "1", ex=ttl_seconds)
        except Exception as exc:  # best-effort: la write no rompe el endpoint.
            _report_degraded("set_flag", exc)

    async def has_flag(self, key: str) -> bool:
        try:
            return bool(await self._redis.exists(key))
        except Exception as exc:  # fail-open: si Redis cae, "no bloqueado".
            _report_degraded("has_flag", exc)
            return False

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as exc:  # best-effort.
            _report_degraded("delete", exc)


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
        # grace marker (item 1 de #142): guarda un VALOR (successor_jti), no solo
        # presencia. grace_key -> (successor_jti, expiry epoch).
        self._grace: dict[str, tuple[str, float]] = {}
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
        for key in [k for k, (_succ, exp) in self._grace.items() if exp <= now]:
            del self._grace[key]

    # --- Blocklist (delegan en las primitivas de flag) ---
    async def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        await self.set_flag(_blocklist_key(jti), ttl_seconds=ttl_seconds)

    async def revoke_if_absent(self, jti: str, *, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            return True  # token ya expirado: no escribir, dejar seguir la rotación.
        # Check-and-set atómico in-process (un solo await, sin yields en el medio):
        # si la blocklist key ya existe y no expiró -> ya estaba revocada -> False.
        self._purge_expired()
        key = _blocklist_key(jti)
        if key in self._flags:
            return False
        self._flags[key] = self._now() + ttl_seconds
        return True

    async def is_revoked(self, jti: str) -> bool:
        return await self.has_flag(_blocklist_key(jti))

    # --- Familia (sid) + grace marker (item 1 de #142) ---
    async def revoke_family(self, sid: str, *, ttl_seconds: int) -> None:
        await self.set_flag(_family_key(sid), ttl_seconds=ttl_seconds)

    async def is_family_revoked(self, sid: str) -> bool:
        return await self.has_flag(_family_key(sid))

    async def set_grace_marker(self, old_jti: str, successor_jti: str, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self._grace[_grace_key(old_jti)] = (successor_jti, self._now() + ttl_seconds)

    async def get_grace_marker(self, old_jti: str) -> str | None:
        self._purge_expired()
        entry = self._grace.get(_grace_key(old_jti))
        return entry[0] if entry is not None else None

    async def auth_status(self, jti: str | None, sid: str | None) -> tuple[bool, bool]:
        # In-memory no tiene RTT que ahorrar: delega en sus propios checks.
        jti_revoked = jti is not None and await self.is_revoked(jti)
        family_revoked = sid is not None and await self.is_family_revoked(sid)
        return (jti_revoked, family_revoked)

    # --- Primitivas genéricas ---
    async def incr_with_ttl(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        self._purge_expired()
        is_new = key not in self._counters
        self._counters[key] = self._counters.get(key, 0) + amount
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
            self._grace.pop(key, None)
