"""CRUD del dominio **Agenda** (ADR-018): ``GET``/``POST``/``PATCH``/``DELETE``
sobre ``/v1/events``.

El front (web + mobile) ya consume estos endpoints contra mocks
(``packages/core/src/features/agenda/api.ts``); acá se vuelven reales. El contrato
del wire vive en ``packages/shared-schemas/src/agenda.ts`` y lo espejan los
schemas ``app/schemas/calendar_event.py`` ("Pydantic gana, Zod sigue").

Las 4 rutas comparten el MISMO aislamiento por usuario: el ``user_id`` sale del
JWT (``CurrentUser``) y todo query filtra por él. Las mutaciones commitean.

Decisiones de diseño (mismas que ``sessions.py``, NO re-litigar):

(1) Aislamiento sin oráculo. Un evento inexistente y un evento de otro usuario dan
    el MISMO 404 (mismo status + mismo ``detail``) en ``PATCH``/``DELETE``; nunca
    se revela la existencia de un evento ajeno. El ``GET /events`` lista SOLO los
    del user (``WHERE user_id == current``) y su ``total`` es el conteo del user.

(2) Orden ``start_at ASC`` (el más próximo primero): el front pinta el día/semana
    de arriba hacia abajo. ``start_at`` siempre existe (``nullable=False``).

(3) ``status`` arranca ``confirmed`` en el create (no se acepta del body). El
    ``EventCreate`` NO trae ``status``; el server lo fija.

(4) Invariante ADR-018 (``recurrence`` exige ``time_zone``). En el ``POST`` la
    enforcea el schema (``EventCreate``). En el ``PATCH`` la enforcea ESTE router
    sobre el estado MERGEADO (la fila ya guardada + el patch): el ``EventPatch`` es
    parcial y no re-valida, pero el evento resultante DEBE satisfacerla → 422 si no.
    NO se expande recurrencia server-side (fase posterior): se guarda como array de
    texto y se devuelve tal cual.

(5) Rate-limit por user_id ANTES de tocar la DB (fail-open). Las 4 rutas comparten
    UN bucket por ``user_id`` (mismo patrón que ``/v1/sessions``): el guard 429 corre
    ANTES de cualquier query, así un usuario throttleado no consume conexiones del
    pool. fail-OPEN si Redis cae (``incr_with_ttl`` => 0 => permite). 429 con
    ``Retry-After`` + ``detail`` neutro (regla #4).

(6) Mirror sin nada de más. ``CalendarEventOut`` NO expone ``user_id`` /
    ``created_at`` / ``updated_at`` (el contrato del front no los declara); el
    envelope ``EventsResponse`` (``items`` + ``total``) vive en
    ``app/schemas/calendar_event_api.py`` (no sagrado).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1._http import too_many_requests
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import check_events_rate_limit
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import CalendarEventOut, EventCreate, EventPatch
from app.schemas.calendar_event_api import EventsResponse
from app.services.calendar import CalendarEventStore, RecurrenceNeedsTimeZoneError

router = APIRouter()

# Default + cap de la paginación de ``GET /v1/events`` (mismo criterio que
# ``/v1/tasks``: default generoso porque el front pinta la agenda entera, el cap
# solo acota el caso patológico de la query sin tope).
_LIMIT_DEFAULT = 100
_LIMIT_MAX = 200

# Detail ÚNICO del 404 de ``PATCH``/``DELETE``: ajeno e inexistente comparten
# exactamente este mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "evento no encontrado"

# Detail del 422 de la invariante ADR-018 sobre el estado mergeado de un PATCH.
_RECURRENCE_TZ_DETAIL = "time_zone es obligatorio en eventos con recurrence."


@router.get("/events", response_model=EventsResponse, status_code=200)
async def list_events(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    limit: Annotated[int, Query(ge=1, le=_LIMIT_MAX)] = _LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventsResponse:
    """Lista los eventos del usuario, ordenados por ``start_at`` ASC.

    - AISLAMIENTO: ``WHERE user_id == current`` en el SELECT y en el COUNT; solo
      los eventos del user, y ``total`` es el conteo COMPLETO del user (no el largo
      de la página) para que el cliente pueda paginar.
    - Orden ``start_at ASC`` (el más próximo primero, decisión #2).
    - Paginación (API-001): ``limit`` ∈ ``[1, 200]`` (default 100), ``offset`` ≥ 0;
      acota la query (antes traía TODOS los eventos sin tope). 422 fuera de rango.
      El front no manda estos params y recibe el default (backward-compatible: el
      shape ``items``/``total`` no cambia).
    - Solo lectura: un SELECT + un COUNT, sin mutar nada.
    - Rate-limit (decisión #5): bucket por ``user_id`` compartido con las 4 rutas,
      ANTES de tocar la DB. fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.

    Returns:
        ``EventsResponse`` con ``items`` (la página) + ``total`` (del user).
    """
    if not await check_events_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().events_window_seconds)
    # Delega la query al store (igual que /tasks): el aislamiento por user_id y el orden
    # viven en CalendarEventStore. El COUNT del total queda inline (mismo patrón que tasks).
    items = await CalendarEventStore(session, user_id).list_all(limit=limit, offset=offset)

    total = await session.scalar(
        select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id == user_id)
    )

    # ``list_all`` devuelve dicts JSON-safe (``_to_result``); se re-hidratan con
    # ``strict=False`` (mismo criterio que /tasks: un str del wire no es instancia de
    # UUID/datetime/enum bajo el strict heredado de YnaraBaseModel).
    return EventsResponse(
        items=[CalendarEventOut.model_validate(item, strict=False) for item in items],
        total=total or 0,
    )


@router.post("/events", response_model=CalendarEventOut, status_code=201)
async def create_event(
    payload: EventCreate,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> CalendarEventOut:
    """Crea un evento del usuario y devuelve el ``CalendarEventOut`` (201).

    - El ``user_id`` sale del JWT (no del body); el ``status`` arranca
      ``confirmed`` (decisión #3).
    - La invariante ADR-018 (``recurrence`` exige ``time_zone``) la valida el
      schema ``EventCreate`` (un cuerpo que la viole da 422 antes de llegar acá).
    - Rate-limit (decisión #5): ANTES de tocar la DB. fail-open si Redis cae.
    - Commitea y devuelve el evento creado.

    Returns:
        ``CalendarEventOut`` del evento recién creado.
    """
    if not await check_events_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().events_window_seconds)
    # add_event INSERTA siempre (no deduplica, a diferencia de la tool del agente): un
    # POST explícito del usuario debe crear el evento. El status arranca confirmed dentro
    # del store; el commit lo da este router.
    created = await CalendarEventStore(session, user_id).add_event(payload)
    await session.commit()

    return CalendarEventOut.model_validate(created, strict=False)


@router.patch("/events/{event_id}", response_model=CalendarEventOut, status_code=200)
async def patch_event(
    event_id: UUID,
    payload: EventPatch,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> CalendarEventOut:
    """Update PARCIAL de un evento del usuario.

    - Busca el evento por id. Si no existe O pertenece a otro usuario -> 404 con el
      MISMO ``detail`` (sin oráculo de existencia ajena, decisión #1).
    - Aplica SOLO los campos enviados (``exclude_unset``): los demás quedan
      intactos. Un ``status``/``time_zone``/``recurrence`` enviados se pisan.
    - Invariante ADR-018 sobre el estado MERGEADO (decisión #4): si tras aplicar
      el patch el evento queda con ``recurrence`` no vacía y sin ``time_zone`` -> 422
      (y NO se commitea).
    - Rate-limit (decisión #5): ANTES de tocar la DB. fail-open si Redis cae.
    - Commitea y devuelve el evento actualizado.

    Returns:
        ``CalendarEventOut`` del evento actualizado.
    """
    if not await check_events_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().events_window_seconds)
    # update_event aplica el patch parcial y enforcea la invariante ADR-018 sobre el estado
    # MERGEADO: si queda con recurrence sin time_zone lanza el domain-error (mapeado acá a
    # 422, sin commit). None = evento inexistente O ajeno -> MISMO 404 (sin oráculo).
    try:
        updated = await CalendarEventStore(session, user_id).update_event(
            event_id, payload.model_dump(exclude_unset=True)
        )
    except RecurrenceNeedsTimeZoneError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_RECURRENCE_TZ_DETAIL,
        ) from None

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()

    return CalendarEventOut.model_validate(updated, strict=False)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: UUID,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> None:
    """Borra un evento del usuario (204, sin body).

    - Busca el evento por id. Si no existe O pertenece a otro usuario -> 404 con el
      MISMO ``detail`` (sin oráculo de existencia ajena, decisión #1).
    - Rate-limit (decisión #5): ANTES de tocar la DB. fail-open si Redis cae.
    - Commitea el borrado y devuelve 204 No Content.
    """
    if not await check_events_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().events_window_seconds)
    # delete_event filtra por user_id (aislamiento): False = evento inexistente O ajeno ->
    # MISMO 404 (sin oráculo de existencia ajena). El commit lo da este router.
    deleted = await CalendarEventStore(session, user_id).delete_event(event_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()
