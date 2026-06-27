"""CRUD del dominio **Recordatorios**: ``GET``/``POST``/``PATCH``/``DELETE`` sobre
``/v1/reminders``.

Recordatorios por-tiempo del usuario (tabla DEDICADA ``reminders``, NO ``tasks``). El
alta también la hace el **agente** por detrás de la conversación (``reminder.set``, ver
``app/llm/tools/reminder.py``); este CRUD HTTP expone la superficie completa para que el
front pueda listar/crear/editar/borrar.

Las 4 rutas comparten el MISMO aislamiento por usuario: el ``user_id`` sale del JWT
(``CurrentUser``) y todo query filtra por él. Las mutaciones commitean.

Decisiones de diseño (mismas que ``events.py`` / ``tasks.py``, NO re-litigar):

(1) Aislamiento sin oráculo. Un recordatorio inexistente y uno de otro usuario dan el
    MISMO 404 en ``PATCH``/``DELETE``; nunca se revela la existencia de uno ajeno. El
    ``GET`` lista SOLO los del user y su ``total`` es el conteo del user.

(2) Orden ``remind_at`` ASC (el más próximo primero).

(3) ``status`` arranca ``pending`` en el create (no se acepta del body). El ``PATCH`` sí
    acepta ``status`` (cancelar / re-activar).

(4) Rate-limit por user_id ANTES de tocar la DB (fail-open). Las 4 rutas comparten UN
    bucket por ``user_id`` (mismo patrón que ``/v1/events``). 429 con ``Retry-After`` +
    ``detail`` neutro (regla #4).

(5) Mirror sin nada de más. ``ReminderOut`` NO expone ``user_id`` / ``created_at`` /
    ``updated_at``; el envelope ``RemindersResponse`` (``items`` + ``total``) vive en
    ``app/schemas/reminder_api.py`` (no sagrado).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1._http import too_many_requests
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import check_reminders_rate_limit
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderCreate, ReminderOut, ReminderPatch
from app.schemas.reminder_api import RemindersResponse
from app.services.reminders import ReminderStore

router = APIRouter()

# Default + cap de la paginación de ``GET /v1/reminders`` (mismo criterio que
# ``/v1/events`` / ``/v1/tasks``).
_LIMIT_DEFAULT = 100
_LIMIT_MAX = 200

# Detail ÚNICO del 404 de ``PATCH``/``DELETE``: ajeno e inexistente comparten exactamente
# este mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "recordatorio no encontrado"


@router.get("/reminders", response_model=RemindersResponse, status_code=200)
async def list_reminders(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    limit: Annotated[int, Query(ge=1, le=_LIMIT_MAX)] = _LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RemindersResponse:
    """Lista los recordatorios del usuario, ordenados por ``remind_at`` ASC.

    - AISLAMIENTO: ``WHERE user_id == current`` en el SELECT (vía ``ReminderStore``) y en
      el COUNT; ``total`` es el conteo COMPLETO del user (para paginar).
    - Paginación: ``limit`` ∈ ``[1, 200]`` (default 100), ``offset`` ≥ 0; 422 fuera de rango.
    - Rate-limit (decisión #4): bucket por ``user_id`` ANTES de tocar la DB. fail-open.

    Returns:
        ``RemindersResponse`` con ``items`` (la página) + ``total`` (del user).
    """
    if not await check_reminders_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().reminders_window_seconds)

    items = await ReminderStore(session, user_id).list_all(limit=limit, offset=offset)

    total = await session.scalar(
        select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id)
    )

    # ``list_all`` devuelve dicts JSON-safe (``_to_result``); se re-hidratan con
    # ``strict=False`` (mismo criterio que /tasks: un str del wire no es instancia de
    # UUID/datetime/enum bajo el strict heredado de YnaraBaseModel).
    return RemindersResponse(
        items=[ReminderOut.model_validate(item, strict=False) for item in items],
        total=total or 0,
    )


@router.post("/reminders", response_model=ReminderOut, status_code=201)
async def create_reminder(
    payload: ReminderCreate,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> ReminderOut:
    """Crea un recordatorio del usuario y devuelve el ``ReminderOut`` (201).

    - El ``user_id`` sale del JWT (no del body); el ``status`` arranca ``pending``
      (decisión #3, server-set).
    - ``add_reminder`` INSERTA siempre (no deduplica, a diferencia de la tool del agente):
      un POST explícito del usuario debe crear el recordatorio.
    - Rate-limit (decisión #4): ANTES de tocar la DB. fail-open.
    - Commitea y devuelve el recordatorio creado.

    Returns:
        ``ReminderOut`` del recordatorio recién creado.
    """
    if not await check_reminders_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().reminders_window_seconds)

    created = await ReminderStore(session, user_id).add_reminder(payload)
    await session.commit()

    return ReminderOut.model_validate(created, strict=False)


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut, status_code=200)
async def patch_reminder(
    reminder_id: UUID,
    payload: ReminderPatch,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> ReminderOut:
    """Update PARCIAL de un recordatorio del usuario.

    - Busca el recordatorio por id. Si no existe O pertenece a otro usuario -> 404 con el
      MISMO ``detail`` (sin oráculo de existencia ajena, decisión #1).
    - Aplica SOLO los campos enviados (``exclude_unset``): ``text`` / ``remind_at`` /
      ``status`` (decisión #3: el PATCH sí acepta ``status``).
    - Rate-limit (decisión #4): ANTES de tocar la DB. fail-open.
    - Commitea y devuelve el recordatorio actualizado.

    Returns:
        ``ReminderOut`` del recordatorio actualizado.
    """
    if not await check_reminders_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().reminders_window_seconds)

    updated = await ReminderStore(session, user_id).update_reminder(
        reminder_id, payload.model_dump(exclude_unset=True)
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()

    return ReminderOut.model_validate(updated, strict=False)


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: UUID,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> None:
    """Borra un recordatorio del usuario (204, sin body).

    - Busca el recordatorio por id. Si no existe O pertenece a otro usuario -> 404 con el
      MISMO ``detail`` (sin oráculo de existencia ajena, decisión #1).
    - Rate-limit (decisión #4): ANTES de tocar la DB. fail-open.
    - Commitea el borrado y devuelve 204 No Content.
    """
    if not await check_reminders_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().reminders_window_seconds)

    deleted = await ReminderStore(session, user_id).delete_reminder(reminder_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()
