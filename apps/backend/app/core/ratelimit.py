"""Rate-limit / lockout aplicativo del login y register (issue #63).

Estrategia: contador con ventana fija (fixed-window por TTL) sobre el bucket
``(ip, email_hash)`` para el login, y por ``ip`` para el register, más un
lockout explícito que se activa al cruzar el threshold.

Funciones puras que reciben el ``store`` (``TokenStore``): testeables con el
``InMemoryTokenStore`` sin Redis. El estado vive SOLO en Redis en prod (sin
tablas, sin alembic).

Decisiones de seguridad (NO re-litigar):

- **Anti-enumeración:** la key del login es ``ip:email_hash``, NO ``email_hash``
  solo. Un lockout de un bucket le dice al atacante "probaste mucho ESTE par
  (ip,email)" — cierto exista o no el email —, no "este email existe". Además el
  endpoint llama ``register_login_failure`` ante CUALQUIER ``user is None``
  (email inexistente incluido, por el diseño anti-enum del service), así que el
  contador sube igual y el 429 llega al MISMO número de intentos exista o no el
  email. No hay oráculo de existencia.

- **PII fuera de la infra (regla #4):** la key usa ``sha256(email)[:32]``, NUNCA
  el email crudo. Una key de Redis con el email sería un leak de PII en la infra.
  Se normaliza con la MISMA normalización que el login (trim + lower) para que
  ``A@X.com`` y ``a@x.com`` colapsen al mismo bucket.

- **fail-OPEN:** todo el cálculo se apoya en ``store`` que ya degrada seguro si
  Redis cae (``incr_with_ttl`` => 0, ``has_flag`` => False). ``check_*`` devuelve
  ``True`` (permitir) y ``register_*`` no rompe. Volvemos al baseline pre-#63
  (login sin freno) en vez de auto-DoSearnos.

Caveat documentado (TODO): ``ip`` es ``request.client.host``; detrás de un
reverse-proxy puede ser la IP del proxy. El fix real (parsear ``X-Forwarded-For``
con allowlist de proxies confiables) se difiere.
"""

from __future__ import annotations

import hashlib

from app.core.config import get_settings
from app.core.token_store import TokenStore

# Prefijos de keys. El email va hasheado (regla #4), nunca crudo.
_LOGIN_COUNTER_PREFIX = "auth:ratelimit:login:"
_LOGIN_LOCKOUT_PREFIX = "auth:lockout:login:"
_REGISTER_COUNTER_PREFIX = "auth:ratelimit:register:"
# Buckets de los rate-limits agregados en S4 (P1 seguridad). El refresh va por
# (ip, sub); chat y export por user_id. El ``sub``/``user_id`` NO se hashea: a
# diferencia del email NO es PII directa (es un UUID opaco, no un identificador
# personal como el mail), así que va crudo en la key — documentado a propósito.
# La IP del refresh tampoco se hashea (es el mismo criterio que login/register).
_REFRESH_COUNTER_PREFIX = "auth:ratelimit:refresh:"
_CHAT_COUNTER_PREFIX = "chat:ratelimit:turn:"
_MEMORY_EXPORT_COUNTER_PREFIX = "memory:ratelimit:export:"


def _normalize_email(email: str) -> str:
    """Trim + lower. IDÉNTICA a la del service (consistencia de bucket con el login)."""
    return email.strip().lower()


def _email_hash(email: str) -> str:
    """sha256 del email normalizado, truncado a 32 hex. NUNCA el email crudo (regla #4)."""
    normalized = _normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _login_counter_key(ip: str, email: str) -> str:
    return f"{_LOGIN_COUNTER_PREFIX}{ip}:{_email_hash(email)}"


def _login_lockout_key(ip: str, email: str) -> str:
    return f"{_LOGIN_LOCKOUT_PREFIX}{ip}:{_email_hash(email)}"


def _register_counter_key(ip: str) -> str:
    return f"{_REGISTER_COUNTER_PREFIX}{ip}"


def _refresh_counter_key(ip: str, sub: str) -> str:
    # sub es un UUID opaco (no PII directa como el email): va crudo, no hasheado.
    return f"{_REFRESH_COUNTER_PREFIX}{ip}:{sub}"


def _chat_counter_key(user_id: str) -> str:
    # user_id es un UUID opaco (no PII directa): va crudo, no hasheado.
    return f"{_CHAT_COUNTER_PREFIX}{user_id}"


def _memory_export_counter_key(user_id: str) -> str:
    # user_id es un UUID opaco (no PII directa): va crudo, no hasheado.
    return f"{_MEMORY_EXPORT_COUNTER_PREFIX}{user_id}"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def check_login_rate_limit(store: TokenStore, *, ip: str, email: str) -> bool:
    """``True`` si el intento de login está permitido; ``False`` si hay lockout activo.

    NO incrementa el contador (eso lo hace ``register_login_failure`` ante un
    fallo). fail-open: si Redis cae, ``has_flag`` devuelve ``False`` y se permite.

    El resultado NO es función de la existencia del email: el contador sube ante
    CUALQUIER fallo (incluido email inexistente, por el diseño anti-enum del
    service), así que el lockout llega al mismo número de intentos exista o no.
    """
    return not await store.has_flag(_login_lockout_key(ip, email))


async def register_login_failure(store: TokenStore, *, ip: str, email: str) -> None:
    """Incrementa el contador de fallos; al cruzar el threshold activa el lockout.

    best-effort (fail-open): si Redis cae, ``incr_with_ttl`` devuelve 0 y no se
    activa el lockout (login sin freno, baseline pre-#63).
    """
    settings = get_settings()
    count = await store.incr_with_ttl(
        _login_counter_key(ip, email),
        ttl_seconds=settings.auth_login_window_seconds,
    )
    if count >= settings.auth_login_max_attempts:
        await store.set_flag(
            _login_lockout_key(ip, email),
            ttl_seconds=settings.auth_login_lockout_seconds,
        )


async def reset_login_rate_limit(store: TokenStore, *, ip: str, email: str) -> None:
    """Login exitoso: limpia contador + lockout de ese bucket (no queda "cerca")."""
    await store.delete(_login_counter_key(ip, email), _login_lockout_key(ip, email))


# ---------------------------------------------------------------------------
# Register (solo por IP — el email aún no existe)
# ---------------------------------------------------------------------------


async def check_register_rate_limit(store: TokenStore, *, ip: str) -> bool:
    """``True`` si el intento de register está permitido; ``False`` si excede el límite.

    A diferencia del login NO hay un lockout separado: se chequea + incrementa el
    contador en una sola operación (el register no tiene "fallo" a contabilizar
    aparte; cada POST cuenta). fail-open: si Redis cae, ``incr_with_ttl`` => 0,
    que es ``<`` al threshold => permite.
    """
    settings = get_settings()
    count = await store.incr_with_ttl(
        _register_counter_key(ip),
        ttl_seconds=settings.auth_register_window_seconds,
    )
    return count <= settings.auth_register_max_attempts


# ---------------------------------------------------------------------------
# Refresh (por (ip, sub) — el sub sale del refresh decodificado)
# ---------------------------------------------------------------------------


async def check_refresh_rate_limit(store: TokenStore, *, ip: str, sub: str) -> bool:
    """``True`` si el ``/auth/refresh`` está permitido; ``False`` si excede el límite.

    Mismo patrón que ``check_register_rate_limit``: chequea + incrementa el contador
    en una sola operación (cada POST cuenta como un intento). El bucket es ``(ip,
    sub)`` para no acoplar usuarios distintos detrás de una misma IP ni una misma
    sesión entre IPs. fail-open: si Redis cae, ``incr_with_ttl`` => 0, que es ``<``
    al threshold => permite (baseline sin freno, nunca auto-DoS).

    El ``sub`` es un UUID opaco (no PII directa como el email): va crudo en la key,
    sin hashear (ver ``_refresh_counter_key``).
    """
    settings = get_settings()
    count = await store.incr_with_ttl(
        _refresh_counter_key(ip, sub),
        ttl_seconds=settings.auth_refresh_window_seconds,
    )
    return count <= settings.auth_refresh_max_attempts


# ---------------------------------------------------------------------------
# Chat (por user_id — del CurrentUser autenticado)
# ---------------------------------------------------------------------------


async def check_chat_rate_limit(store: TokenStore, *, user_id: str) -> bool:
    """``True`` si el turno de chat está permitido; ``False`` si excede el límite.

    Bucket por ``user_id`` (el JWT ya lo autenticó): el freno es por usuario, no por
    IP, así no penaliza a varios usuarios tras un NAT compartido. Chequea +
    incrementa en una sola op. fail-open: si Redis cae, ``incr_with_ttl`` => 0 =>
    permite (baseline sin freno).

    El ``user_id`` es un UUID opaco (no PII directa): va crudo en la key, sin
    hashear (ver ``_chat_counter_key``).
    """
    settings = get_settings()
    count = await store.incr_with_ttl(
        _chat_counter_key(user_id),
        ttl_seconds=settings.chat_window_seconds,
    )
    return count <= settings.chat_max_requests


# ---------------------------------------------------------------------------
# Memory export (por user_id — del CurrentUser autenticado)
# ---------------------------------------------------------------------------


async def check_memory_export_rate_limit(store: TokenStore, *, user_id: str) -> bool:
    """``True`` si el export de memoria está permitido; ``False`` si excede el límite.

    Bucket por ``user_id`` para el endpoint más caro (descifra las 3 capas sin
    paginar): un techo de pocas por hora corta el abuso sin molestar un export
    legítimo. Chequea + incrementa en una sola op. fail-open: si Redis cae,
    ``incr_with_ttl`` => 0 => permite (baseline sin freno).

    El ``user_id`` es un UUID opaco (no PII directa): va crudo en la key, sin
    hashear (ver ``_memory_export_counter_key``).
    """
    settings = get_settings()
    count = await store.incr_with_ttl(
        _memory_export_counter_key(user_id),
        ttl_seconds=settings.memory_export_window_seconds,
    )
    return count <= settings.memory_export_max_requests
