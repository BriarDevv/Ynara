"""Registro de device tokens para push: ``POST`` / ``DELETE`` sobre ``/v1/devices``.

El front (web + mobile) registra el token de push de cada dispositivo acá; el scheduler
de recordatorios (``app/workflows/reminder_dispatch.py``) los usa para despachar avisos.

Decisiones de diseño:

(1) **Unregister por BODY, no por path** (regla #4): el ``token`` es una credencial de
    envío, no debe viajar en la URL (quedaría en logs de acceso / historial). Por eso
    ``DELETE /v1/devices`` toma ``{token}`` en el body (``DeviceUnregister``), no
    ``DELETE /v1/devices/{token}``.

(2) **Upsert idempotente** en el register: re-registrar el mismo ``token`` re-asigna el
    dueño (``DeviceTokenStore.register``) en vez de fallar por el UNIQUE. Devuelve 201
    cuando crea una fila nueva, 200 cuando re-asigna una existente.

(3) **Aislamiento sin oráculo**: un token inexistente y uno de otro usuario dan el MISMO
    404 en el ``DELETE`` (sin revelar la existencia de un token ajeno).

(4) **Sin rate-limit** (precedente ``users.py`` PATCH): son writes de bajo costo sobre la
    propia fila, sin vector de enumeración ni de DoS. Omisión deliberada.

(5) Mirror sin nada de más: ``DeviceTokenOut`` NO expone ``user_id``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.device import DeviceRegister, DeviceTokenOut, DeviceUnregister
from app.services.devices import DeviceTokenStore, TooManyDeviceTokensError

router = APIRouter()

# Detail ÚNICO del 404 del ``DELETE``: token ajeno e inexistente comparten exactamente
# este mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "device token no encontrado"

# Detail genérico del 429 del cap de tokens por usuario (regla #4: sin datos del usuario).
_TOO_MANY_TOKENS_DETAIL = "demasiados device tokens registrados"


@router.post("/devices", response_model=DeviceTokenOut)
async def register_device(
    payload: DeviceRegister,
    session: DbSession,
    user_id: CurrentUser,
    response: Response,
) -> DeviceTokenOut:
    """Registra (upsert) un device token del usuario.

    - El ``user_id`` sale del JWT (no del body). Upsert por ``token``: si ya existe se
      re-asigna al user actual (decisión #2), si no se INSERTA.
    - **201** cuando crea una fila nueva; **200** cuando re-asigna una existente. El
      ``register`` devuelve ``created`` (``existing is None``), así que el status code se
      decide atómicamente, sin un read previo (sin TOCTOU).
    - **429** si el usuario ya alcanzó ``MAX_DEVICE_TOKENS_PER_USER`` y registra uno NUEVO
      (un re-registro de uno existente nunca da 429).
    - Commitea y devuelve el ``DeviceTokenOut``.

    Returns:
        ``DeviceTokenOut`` del device registrado.
    """
    store = DeviceTokenStore(session, user_id)
    try:
        created, was_created = await store.register(payload)
    except TooManyDeviceTokensError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_TOO_MANY_TOKENS_DETAIL,
        ) from None
    await session.commit()

    response.status_code = status.HTTP_201_CREATED if was_created else status.HTTP_200_OK
    return DeviceTokenOut.model_validate(created, strict=False)


@router.delete("/devices", status_code=204)
async def unregister_device(
    payload: DeviceUnregister,
    session: DbSession,
    user_id: CurrentUser,
) -> None:
    """Des-registra un device token del usuario (204, sin body).

    - El ``token`` viaja por BODY (decisión #1, regla #4): es una credencial, no va en la
      URL.
    - Borra el token SOLO si es del user (aislamiento). Si no existe O es de otro usuario
      -> 404 con el MISMO ``detail`` (sin oráculo de existencia ajena, decisión #3).
    - Commitea el borrado y devuelve 204 No Content.
    """
    deleted = await DeviceTokenStore(session, user_id).unregister(payload.token)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()
