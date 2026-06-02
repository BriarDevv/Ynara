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

(d) Rate-limit / lockout aplicativo (issue #63 + S4 P1 seguridad). ``/auth/token``
    limita por ``(ip, email_hash)``, ``/auth/register`` por ``ip`` y ``/auth/refresh``
    por ``(ip, sub)`` (ver ``app/core/ratelimit.py``). El 429 no da oráculo de
    enumeración. fail-OPEN si Redis cae (sin freno, baseline). El rate-limit
    aplicativo es una capa más; bcrypt (caro por intento) + WAF/reverse-proxy siguen
    siendo defensa de fondo.

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
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.v1._http import too_many_requests
from app.core.config import Settings, get_settings
from app.core.deps import (
    UNAUTHORIZED_DETAIL,
    CurrentClaims,
    CurrentUser,
    DbSession,
    TokenStoreDep,
)
from app.core.ratelimit import (
    check_login_rate_limit,
    check_refresh_rate_limit,
    check_register_rate_limit,
    register_login_failure,
    reset_login_rate_limit,
)
from app.core.security import (
    SID_CLAIM,
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


def _unauthorized() -> HTTPException:
    """401 uniforme (mismo shape que ``get_current_user``). detail estático (regla #4).

    Reusa ``UNAUTHORIZED_DETAIL`` (en ``deps.py``) a propósito: el 401 de un token malo
    y el de credenciales de login deben ser indistinguibles (anti-enumeración).
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHORIZED_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _ttl_from_exp(payload: dict) -> int:
    """Segundos restantes hasta el ``exp`` del token (floor a 0). Para el TTL del blocklist."""
    exp = int(payload["exp"])
    now = int(datetime.now(UTC).timestamp())
    return max(exp - now, 0)


def _refresh_ttl_seconds(settings: Settings) -> int:
    """TTL completo del refresh en segundos (vida de la familia, item 1 de #142).

    La family-revocation usa el TTL COMPLETO del refresh, NO el remaining del token
    que disparó el reuse: la familia debe sobrevivir al refresh vivo más largo que
    pudo emitirse en ella (un hermano más nuevo no debe sobrevivir a la key de
    revocación). Self-expira sin GC.
    """
    return settings.jwt_refresh_expire_minutes * 60


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
    settings = get_settings()
    if not await check_register_rate_limit(store, ip=_client_ip(request)):
        raise too_many_requests(settings.auth_register_window_seconds)
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
        raise too_many_requests(get_settings().auth_login_lockout_seconds)
    user = await authenticate_user(session, email=body.email, password=body.password)
    if user is None:
        await register_login_failure(store, ip=ip, email=body.email)
        raise _unauthorized()
    await reset_login_rate_limit(store, ip=ip, email=body.email)
    # Cada login nace una sesión nueva (sid uuid4) que va en AMBOS tokens: agrupa
    # el access + todos los refresh rotados bajo una única unidad de revocación
    # (familia). El logout-de-sesión y la reuse-detection del refresh la matan de
    # una (item 1 de #142).
    sid = uuid4().hex
    return TokenOut(
        access_token=create_access_token(str(user.id), {SID_CLAIM: sid}),
        refresh_token=create_refresh_token(str(user.id), {SID_CLAIM: sid}),
    )


@router.post("/auth/refresh", response_model=TokenOut, status_code=status.HTTP_200_OK)
async def refresh(body: RefreshRequest, store: TokenStoreDep, request: Request) -> TokenOut:
    """Rota un refresh token: devuelve access + refresh nuevos. 200, 401 o 429.

    El refresh es **single-use** con **reuse-detection a nivel familia (sid)**,
    retry-safe (item 1 de #142). Ramas:

    0. **familia revocada:** si el ``sid`` del refresh ya fue revocado (logout-de-
       sesión o un breach previo), NO rota -> 401. ``/refresh`` no pasa por
       ``get_current_claims``, así que este chequeo es explícito (de lo contrario un
       logout no mataría el refresh que no se mandó en el body).

    1. **first-use (camino feliz):** el gate atómico ``revoke_if_absent`` (SET NX
       EX, cierra el TOCTOU de rotaciones concurrentes) blocklistea el ``jti`` viejo
       SOLO si no estaba ya revocado. Si gana el claim, mintea un par nuevo
       propagando el ``sid`` (familia) y deja un **grace marker** corto apuntando al
       sucesor (para que un retry de red benigno sea idempotente).

    2. **benign-retry (dentro del grace):** si NO ganó el claim (ya estaba revocado)
       PERO existe el grace marker, es un reenvío del MISMO refresh dentro de la
       ventana (timeout TCP móvil + retry). NO se revoca la familia: se re-mintea un
       par usable de la misma familia. El ``jti`` viejo sigue muerto (no se
       des-revoca); como toda la familia se mata de una vía ``sid``, re-mintear no
       agranda el blast-radius.

    3. **breach (reuse fuera del grace):** si NO ganó el claim y NO hay grace marker,
       un refresh ya rotado resurgió tarde -> replay/robo. Se revoca la familia
       ENTERA (mata el refresh + todos los access hermanos vía ``get_current_claims``)
       y se da 401.

    Compat: un refresh sin ``sid`` (pre-item 1) cae a la rama 1 arrancando una
    familia nueva; reusarlo cae a la rama 3 SIN family-revoke (no hay sid que matar)
    -> degrada al single-use de #142 sin nukear nada imposible.

    Rate-limit (S4, P1 seguridad): bucket por ``(ip, sub)``. Tras validar firma +
    ``sub`` (un token basura ya dio 401 antes), si se cruza el techo de la ventana ->
    429 con ``Retry-After`` (mismo shape que el login). El refresh es rotación
    legítima frecuente, así que el techo es MÁS permisivo que el del login. fail-open
    si Redis cae (rota sin freno, baseline).

    fail-open: ``revoke_if_absent`` True si Redis cae (rota igual);
    ``get_grace_marker`` None si Redis cae (un retry cae a rama 3 pero
    ``revoke_family`` también es no-op -> 401 sin revocación persistente).

    Regla #4: 401 uniforme; ni jose, ni el token, ni el ``jti``/``sid`` se loguean
    ni se devuelven (``verify_token`` deja el detalle de jose solo en ``__cause__``).
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
    sid = payload.get(SID_CLAIM)
    settings = get_settings()

    # Rate-limit por (ip, sub) (S4, P1 seguridad): el endpoint era público sin
    # freno. Va DESPUÉS de validar la firma + sub (un token basura ya dio 401, no
    # entra acá) y ANTES de tocar Redis para rotar: un sub identificado que abusa
    # del refresh se frena temprano. fail-open si Redis cae (rota sin freno,
    # baseline). El 429 usa el mismo shape que el login (Retry-After con la ventana
    # del refresh). No introduce oráculo: el 401 de firma mala ya ocurrió antes.
    if not await check_refresh_rate_limit(store, ip=_client_ip(request), sub=sub):
        raise too_many_requests(settings.auth_refresh_window_seconds)

    # --- RAMA 0: familia ya revocada (logout-de-sesión o breach previo) ---
    # /refresh NO pasa por get_current_claims, así que el family-check del access
    # no lo cubre: lo hacemos explícito acá. Un refresh cuya familia murió NO rota
    # (si no, un logout no mataría el refresh que no fue al body). Se chequea ANTES
    # del gate atómico para que una familia muerta jamás re-mintee. fail-open: si
    # Redis cae, is_family_revoked devuelve False -> se cae al baseline (rota igual).
    if sid is not None and await store.is_family_revoked(sid):
        raise _unauthorized()

    # --- RAMA 1: first-use (gate atómico gana el claim) ---
    if await store.revoke_if_absent(old_jti, ttl_seconds=_ttl_from_exp(payload)):
        new_refresh_jti = uuid4().hex
        # Grace marker ANTES de responder, apuntando al sucesor: habilita el
        # retry-safe (rama 2). Solo tiene sentido con sid (sin familia no hay
        # retry-safe que ofrecer).
        if sid is not None:
            await store.set_grace_marker(
                old_jti,
                new_refresh_jti,
                ttl_seconds=settings.auth_refresh_reuse_grace_seconds,
            )
        # Propaga el sid; si faltaba (token pre-item 1), arranca una familia nueva.
        new_sid = sid if sid is not None else uuid4().hex
        return TokenOut(
            access_token=create_access_token(sub, {SID_CLAIM: new_sid}),
            refresh_token=create_refresh_token(sub, {SID_CLAIM: new_sid}, jti=new_refresh_jti),
        )

    # Llegamos acá: revoke_if_absent devolvió False => old_jti YA estaba revocado.
    # --- RAMA 2: benign-retry idempotente (dentro del grace) ---
    successor_jti = await store.get_grace_marker(old_jti) if sid is not None else None
    if successor_jti is not None:
        # Retry de red: el cliente reenvió el mismo refresh dentro de la ventana.
        # Idempotencia REAL: el refresh re-emitido reusa el jti del sucesor canónico
        # (el que minteó la rama 1), así TODOS los retries de ``old_jti`` convergen
        # en UNA sola cadena en vez de forkear la familia en ramas paralelas que
        # evadirían la reuse-detection hasta el exp natural (30d). El ``jti`` viejo
        # sigue blocklisteado (no se des-revoca); un reuse posterior del sucesor
        # fuera de SU propio grace vuelve a caer en la rama 3 (breach) y la familia
        # se revoca. El access es nuevo (independiente, vida corta propia).
        return TokenOut(
            access_token=create_access_token(sub, {SID_CLAIM: sid}),
            refresh_token=create_refresh_token(sub, {SID_CLAIM: sid}, jti=successor_jti),
        )

    # --- RAMA 3: breach (reuse fuera del grace) ---
    if sid is not None:
        await store.revoke_family(sid, ttl_seconds=_refresh_ttl_seconds(settings))
    raise _unauthorized()


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    store: TokenStoreDep,
    claims: CurrentClaims,
) -> Response:
    """Revoca la sesión actual (familia entera) + el refresh del body. 204 No Content.

    Si el access trae ``sid`` (item 1 de #142), revoca la FAMILIA entera de esa
    sesión: el refresh, el access actual y cualquier access hermano dejan de servir
    (vía ``get_current_claims`` -> ``auth_status`` -> family_revoked). Otras sesiones
    (otro device, otro login con distinto ``sid``) quedan intactas: blast-radius
    mínimo. La family-revocation usa el TTL completo del refresh (la familia
    sobrevive a cualquier jti).

    Se mantienen ADEMÁS los ``revoke`` por ``jti`` individuales (access del header +
    refresh del body): para un token pre-item 1 SIN ``sid`` no hay familia que matar,
    así que el revoke por jti sigue siendo su única defensa. Con ``sid`` presente son
    redundantes (la familia ya los cubre) pero inofensivos y baratos -> compat sin
    ramas extra.

    Un refresh inválido en el body se IGNORA en silencio: logout es idempotente y
    best-effort, un token basura no debe dar error.

    Regla #4: no se loguea ni se devuelve ningún token/jti/sid crudo. fail-open: si
    Redis cae al escribir, el logout "falla en silencio" (el store es best-effort)
    pero el token expira solo.
    """
    sid = claims.get("sid")
    if sid is not None:
        await store.revoke_family(sid, ttl_seconds=_refresh_ttl_seconds(get_settings()))
    access_jti = claims.get("jti")
    if access_jti is not None:
        await store.revoke(access_jti, ttl_seconds=_ttl_from_exp(claims))
    if body.refresh_token is not None:
        try:
            refresh_payload = verify_token(body.refresh_token, expected_type="refresh")
        except InvalidTokenError:
            refresh_payload = None  # best-effort: refresh basura no rompe el logout.
        if refresh_payload is not None and refresh_payload.get("jti") is not None:
            await store.revoke(refresh_payload["jti"], ttl_seconds=_ttl_from_exp(refresh_payload))
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
            detail=UNAUTHORIZED_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserOut.model_validate(user)
