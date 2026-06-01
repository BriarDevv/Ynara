"""Endpoints HTTP del módulo de auth: ``/v1/auth/register`` y ``/v1/auth/token``.

JSON-only (sin OAuth2PasswordRequestForm / python-multipart): el front manda
``{email, password}`` como JSON. El trabajo de dominio (hashing, normalización,
verificación, anti-enumeración) vive en ``app/services/auth.py``; estos handlers
solo orquestan request -> service -> commit -> response wire.

Decisiones de seguridad (criticadas adversarialmente, NO re-litigar):

(a) Anti-enumeración en login. ``/auth/token`` devuelve EXACTAMENTE el mismo 401
    (status + ``detail`` + header ``WWW-Authenticate: Bearer``) tanto si el email
    no existe como si el password es incorrecto. NUNCA un 404. Sumado al
    timing-safe del service (dummy hash cuando el usuario no existe), no hay
    oráculo de enumeración por status, body ni timing en el login.

(b) Register 409 es un trade-off de enumeración CONSCIENTE. ``/auth/register``
    devuelve 409 ante un email ya registrado, lo que técnicamente revela que ese
    email existe. Se acepta a propósito en un despliegue on-prem / mono-tenant:
    el alternativo (aceptar siempre y mandar un mail de "ya tenés cuenta") exige
    infra de mail que el MVP no tiene, y el valor de UX de un error claro de
    duplicado supera el riesgo de enumeración en este contexto.

(c) Revocación con blocklist Redis (issue #63). ``/auth/logout`` blocklistea el
    ``jti`` del access (y del refresh si viene): ese token deja de servir aunque
    no haya expirado. ``/auth/refresh`` rota el refresh (single-use) y detecta
    reuse del viejo. El estado vive SOLO en Redis (sin tablas), con TTL =
    vida-restante del token (self-expire, sin GC). fail-OPEN: si Redis cae se
    pierde la revocación anticipada pero NO se rompe auth (se vuelve al baseline
    JWT-stateless: el token vale hasta su ``exp`` natural). Ver ENDPOINTS.md.

(d) Rate-limit / lockout aplicativo (issue #63). ``/auth/token`` limita por
    ``(ip, email_hash)`` y ``/auth/register`` por ``ip`` (ver
    ``app/core/ratelimit.py``). El 429 no da oráculo de enumeración. fail-OPEN si
    Redis cae (login sin freno, baseline pre-#63). El rate-limit aplicativo es una
    capa más; bcrypt (caro por intento) + WAF/reverse-proxy siguen siendo defensa
    de fondo.

(e) ``GET /auth/me`` es la PROPIA identidad, no un recurso ajeno. Si el ``sub`` del
    JWT (token válido) ya no tiene fila (user borrado, caso raro), se devuelve 401
    con ``WWW-Authenticate: Bearer`` —la identidad caducó, re-autenticarse— y NO un
    404: un 404 sugeriría un recurso ausente, no una identidad inválida. El
    aislamiento "ajena == inexistente → 404 sin oráculo" de ``/sessions/{id}`` /
    ``/memory`` aplica a recursos de OTROS users, no a la identidad del propio token.

Regla #4: ningún password ni hash llega a logs, respuestas ni excepciones. El
422 de Pydantic puede ecoar el ``input`` del campo que falló; en register el
campo que típicamente falla por longitud es ``password``, así que ese eco se
neutraliza con un exception handler de validación montado en ``app/main.py``
(scrubbea ``password`` del detalle). Ver el test ``test_no_leak_password_en_errores``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentClaims, CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import (
    check_login_rate_limit,
    check_register_rate_limit,
    register_login_failure,
    reset_login_rate_limit,
)
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenOut,
)
from app.schemas.user import UserOut
from app.services.auth import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
)

router = APIRouter()


def _client_ip(request: Request) -> str:
    """IP del cliente para el rate-limit. ``"unknown"`` si no hay client info.

    Caveat (TODO): detrás de un reverse-proxy esto puede ser la IP del proxy; el
    fix real (parsear ``X-Forwarded-For`` con allowlist de proxies confiables) se
    difiere. Por ahora es una defensa aplicativa básica.
    """
    return request.client.host if request.client else "unknown"


def _too_many_requests() -> HTTPException:
    """429 uniforme del rate-limit, sin oráculo de enumeración (ver docstring del módulo)."""
    settings = get_settings()
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="demasiados intentos, intente mas tarde",
        headers={"Retry-After": str(settings.auth_login_lockout_seconds)},
    )


def _unauthorized() -> HTTPException:
    """401 uniforme (mismo shape que ``get_current_user``). detail estático (regla #4)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _ttl_from_exp(payload: dict) -> int:
    """Segundos restantes hasta el ``exp`` del token (floor a 0). Para el TTL del blocklist."""
    exp = int(payload["exp"])
    now = int(datetime.now(UTC).timestamp())
    return max(exp - now, 0)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: DbSession,
    store: TokenStoreDep,
    request: Request,
) -> UserOut:
    """Registra un usuario nuevo. 201 con ``UserOut``; 409 si el email ya existe.

    El service crea + flushea (sin commit); este handler commitea al final
    (patrón ``chat.py``). Ante ``EmailAlreadyRegisteredError`` el service YA hizo
    ``rollback``, así que la sesión está limpia para responder el 409.

    Rate-limit por IP (issue #63): un freno laxo contra el registro masivo. Es la
    primera barrera, ANTES de tocar la DB. fail-open si Redis cae.

    Mapeo de errores: 429 rate-limit (por IP), 422 validación (Pydantic,
    automático), 409 email duplicado (trade-off de enumeración consciente, ver
    docstring del módulo), 201 éxito.
    """
    if not await check_register_rate_limit(store, ip=_client_ip(request)):
        raise _too_many_requests()
    try:
        user = await register_user(
            session,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except EmailAlreadyRegisteredError as exc:
        # register_user YA hizo rollback: la sesión está usable. detail neutro,
        # sin password ni hash (regla #4).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email ya registrado",
        ) from exc
    await session.commit()
    return UserOut.model_validate(user)


@router.post("/auth/token", response_model=TokenOut, status_code=status.HTTP_200_OK)
async def token(
    body: LoginRequest,
    session: DbSession,
    store: TokenStoreDep,
    request: Request,
) -> TokenOut:
    """Verifica credenciales y devuelve access + refresh token. 200, 401 o 429.

    Anti-enumeración: el MISMO 401 (status + ``detail`` + ``WWW-Authenticate:
    Bearer``) para email inexistente y para password incorrecto; el service ya
    corre el dummy hash en el camino "usuario inexistente" para que el timing
    también sea uniforme. NUNCA un 404.

    Rate-limit / lockout (issue #63): el bucket es ``(ip, email_hash)``. Tras
    ``auth_login_max_attempts`` fallos en la ventana, el bucket queda en lockout y
    da 429 inmediato (sin tocar la DB ni bcrypt). El 429 NO es función de la
    existencia del email: ``register_login_failure`` se llama ante CUALQUIER
    ``user is None`` (incluido email inexistente, por el diseño anti-enum del
    service), así que el lockout llega al mismo número de intentos exista o no el
    email. No hay oráculo. fail-open si Redis cae (login sin freno, baseline
    pre-#63). Un login OK resetea el contador del bucket.

    Mapeo de errores: 429 lockout, 422 validación (Pydantic, automático), 401
    credenciales inválidas (uniforme), 200 éxito con access + refresh.
    """
    ip = _client_ip(request)
    if not await check_login_rate_limit(store, ip=ip, email=body.email):
        raise _too_many_requests()
    user = await authenticate_user(session, email=body.email, password=body.password)
    if user is None:
        await register_login_failure(store, ip=ip, email=body.email)
        raise _unauthorized()
    await reset_login_rate_limit(store, ip=ip, email=body.email)
    return TokenOut(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/auth/refresh", response_model=TokenOut, status_code=status.HTTP_200_OK)
async def refresh(body: RefreshRequest, store: TokenStoreDep) -> TokenOut:
    """Rota un refresh token: devuelve access + refresh nuevos. 200 o 401.

    El refresh es **single-use**: cada ``/refresh`` blocklistea el refresh
    consumido (su ``jti``) y entrega uno nuevo. Reusar el refresh viejo cae en la
    detección de reuse (paso de ``is_revoked``) y da 401 — un refresh ya rotado
    que vuelve a aparecer es replay/robo.

    El refresh emitido en ``/token`` nace "limpio" (su ``jti`` no se registra): el
    modelo es **blocklist** (deny-list), un refresh es válido mientras NO esté
    blocklisteado y su firma/exp/type sean correctos.

    Regla #4: 401 uniforme; el detalle de ``jose`` NUNCA se loguea ni se devuelve
    (``verify_token`` ya lo deja solo en ``__cause__``).

    TODO (diferido por scope): blocklistear toda la FAMILIA del token ante un
    reuse (requiere un claim ``family``/``sid``).
    """
    try:
        payload = verify_token(body.refresh_token, expected_type="refresh")
    except InvalidTokenError as exc:
        raise _unauthorized() from exc
    old_jti = payload.get("jti")
    sub = payload.get("sub")
    if old_jti is None or sub is None:
        # Un refresh sin jti/sub no es rotable: los refresh siempre nacen con
        # ambos, así que su ausencia es sospechosa -> 401 uniforme.
        raise _unauthorized()
    # Detección de reuse: si el viejo YA está blocklisteado, fue rotado antes y se
    # está reusando (robo/replay). 401 uniforme, sin revelar "reuse detectado".
    if await store.is_revoked(old_jti):
        raise _unauthorized()
    # Rotar: blocklistear el refresh consumido con su vida restante (self-expire).
    await store.revoke(old_jti, ttl_seconds=_ttl_from_exp(payload))
    return TokenOut(
        access_token=create_access_token(sub),
        refresh_token=create_refresh_token(sub),
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    store: TokenStoreDep,
    claims: CurrentClaims,
) -> Response:
    """Revoca el access actual (y el refresh si viene). 204 No Content.

    Blocklistea el ``jti`` del access del header ``Authorization`` con su vida
    restante: ese mismo access deja de servir en ``/me``/``/chat`` (vía
    ``get_current_user``). Si el access es viejo (sin ``jti``) -> no-op (no rompe).

    Si ``body.refresh_token`` viene y es válido, también se blocklistea su ``jti``.
    Un refresh inválido en el body se IGNORA en silencio: logout es idempotente y
    best-effort, un token basura no debe dar error.

    Regla #4: no se loguea ni se devuelve ningún token crudo. fail-open: si Redis
    cae al escribir, el logout "falla en silencio" (el store es best-effort) pero
    el token expira solo.
    """
    access_jti = claims.get("jti")
    if access_jti is not None:
        await store.revoke(access_jti, ttl_seconds=_ttl_from_exp(claims))
    if body.refresh_token is not None:
        try:
            refresh_payload = verify_token(body.refresh_token, expected_type="refresh")
        except InvalidTokenError:
            refresh_payload = None  # best-effort: refresh basura no rompe el logout.
        if refresh_payload is not None and refresh_payload.get("jti") is not None:
            await store.revoke(
                refresh_payload["jti"], ttl_seconds=_ttl_from_exp(refresh_payload)
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def me(session: DbSession, user_id: CurrentUser) -> UserOut:
    """Devuelve el ``UserOut`` de la identidad autenticada. 200 o 401.

    El ``user_id`` sale del JWT (``CurrentUser``, ya validado por
    ``get_current_user``: 401 si el token falta / es invalido / expiro). Se busca
    el ``User`` por ese id (``session.get``).

    401, NO 404, si el user no existe. Es la PROPIA identidad, no un lookup de
    recurso ajeno: un token valido cuyo ``sub`` ya no tiene fila (user borrado,
    caso raro) representa una identidad que dejo de existir, asi que la respuesta
    correcta es 401 con ``WWW-Authenticate: Bearer`` (re-autenticarse), igual que
    un token invalido. Un 404 sugeriria erroneamente un recurso ausente y no la
    identidad caduca; ademas el aislamiento de ``/sessions/{id}`` (404 sin oraculo)
    aplica a recursos AJENOS, no a la identidad propia.

    Regla #4: ``UserOut`` nunca expone ``password_hash`` (no es campo del schema),
    asi que la respuesta no filtra credenciales.

    Returns:
        ``UserOut`` del usuario autenticado (sin nada sensible).
    """
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credenciales invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserOut.model_validate(user)
