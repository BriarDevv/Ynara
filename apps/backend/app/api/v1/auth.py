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

(c) JWT stateless: logout es un no-op honesto. No hay store de tokens revocados;
    la única ventana de revocación es el TTL del access token
    (``settings.jwt_expire_minutes``). Por eso ``/refresh`` y ``/logout`` quedan
    diferidos en vez de implementarse como mentiras (un ``/logout`` que no
    invalida nada). Ver ENDPOINTS.md.

(d) Rate-limit es TODO. El MVP no agrega dependencias (sin slowapi / Redis), así
    que estos endpoints NO tienen rate-limit todavía: un atacante puede probar
    passwords sin freno aplicativo. Es deuda conocida y documentada; mitigarlo
    (slowapi / WAF / reverse-proxy) es trabajo posterior.

Regla #4: ningún password ni hash llega a logs, respuestas ni excepciones. El
422 de Pydantic puede ecoar el ``input`` del campo que falló; en register el
campo que típicamente falla por longitud es ``password``, así que ese eco se
neutraliza con un exception handler de validación montado en ``app/main.py``
(scrubbea ``password`` del detalle). Ver el test ``test_no_leak_password_en_errores``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut
from app.schemas.user import UserOut
from app.services.auth import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
)

router = APIRouter()


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: DbSession) -> UserOut:
    """Registra un usuario nuevo. 201 con ``UserOut``; 409 si el email ya existe.

    El service crea + flushea (sin commit); este handler commitea al final
    (patrón ``chat.py``). Ante ``EmailAlreadyRegisteredError`` el service YA hizo
    ``rollback``, así que la sesión está limpia para responder el 409.

    Mapeo de errores: 422 validación (Pydantic, automático), 409 email duplicado
    (trade-off de enumeración consciente, ver docstring del módulo), 201 éxito.
    """
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
async def token(body: LoginRequest, session: DbSession) -> TokenOut:
    """Verifica credenciales y devuelve un access token JWT. 200 o 401.

    Anti-enumeración: el MISMO 401 (status + ``detail`` + ``WWW-Authenticate:
    Bearer``) para email inexistente y para password incorrecto; el service ya
    corre el dummy hash en el camino "usuario inexistente" para que el timing
    también sea uniforme. NUNCA un 404.

    Mapeo de errores: 422 validación (Pydantic, automático), 401 credenciales
    inválidas (uniforme), 200 éxito con el token.
    """
    user = await authenticate_user(session, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credenciales invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(str(user.id)))
