"""Perfil del usuario: ``PATCH /v1/users/me``.

Escritura parcial del propio perfil (``display_name``, ``onboarding_completed``,
``retention_sensitive_days``). Es la identidad **PROPIA** (``CurrentUser`` del
JWT), no un recurso ajeno: el ``GET`` de la identidad vive en ``/v1/auth/me``;
acá va la edición. Sin migración (las columnas ya existen) y sobre la tabla
``users`` (operativa, **no** sagrada — regla #3 no aplica).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.deps import UNAUTHORIZED_DETAIL, CurrentUser, DbSession
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter()


@router.patch("/users/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def update_me(
    payload: UserUpdate,
    session: DbSession,
    user_id: CurrentUser,
) -> UserOut:
    """Update parcial del perfil propio. 200 con el ``UserOut`` actualizado.

    - ``user_id`` sale del JWT (``CurrentUser``): 401 si el token falta / es
      inválido / expiró (lo resuelve ``get_current_user`` antes de entrar acá).
    - Solo se tocan los campos **enviados con valor no nulo** (``exclude_none``):
      un PATCH sin campos es un no-op idempotente y NO se puede pisar con ``null``
      un campo NOT NULL (``onboarding_completed`` / ``retention_sensitive_days``).
      Los rangos los valida ``UserUpdate`` (``display_name`` ≤40,
      ``retention_sensitive_days`` 30-365 → 422 fuera de rango).
    - 401 (no 404) si el ``sub`` válido ya no tiene fila: es la identidad PROPIA
      caduca, mismo criterio que ``/v1/auth/me`` (re-autenticarse).
    - **Sin rate-limit** (a diferencia de sessions/memory, que sí lo tienen): es un
      write de bajo costo sobre la PROPIA fila (un UPDATE puntual), sin vector de
      enumeración ni de DoS (no escanea ni dispara trabajo caro). Omisión
      deliberada; si se quisiera cobertura uniforme con el resto de los endpoints
      autenticados, sumar un bucket por ``user_id`` (patrón
      ``check_sessions_rate_limit``) es trivial.

    Regla #4: ``UserOut`` nunca expone ``password_hash`` (no es campo del schema).
    """
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(user, field, value)

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
