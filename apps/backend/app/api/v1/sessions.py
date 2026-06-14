"""Read + lifecycle de la ``ChatSession``: ``GET /v1/sessions``,
``GET /v1/sessions/{id}`` y ``POST /v1/sessions/{id}/close``.

Las dos read surfaces (list paginado + detail) y el cierre lifecycle comparten
el MISMO aislamiento por usuario: el ``user_id`` sale del JWT (``CurrentUser``) y
todo query filtra por el. El close ademas setea ``ended_at`` (trigger que mas
adelante, M10 Ola 4, dispara la consolidacion episodica); aca entrega SOLO el
lifecycle, sin tocar memoria ni encolar nada.

Decisiones de diseno (criticadas, NO re-litigar):

(1) Aislamiento por usuario, sin oraculo. Una sesion inexistente y una sesion de
    otro usuario dan el MISMO 404 (mismo status + mismo ``detail``); nunca se
    revela la existencia de una sesion ajena. El ``GET /sessions`` lista SOLO las
    del user (``WHERE user_id == current``) y su ``total`` es el conteo del user.
    El ``GET /sessions/{id}`` ajeno da el mismo 404 que uno inexistente. Identico
    al patron de ``resolve_chat_session`` en ``app/api/v1/_sessions.py``.

(2) Solo lectura en los GET. Ningun GET muta ni encola nada: ``GET /sessions``
    arma la pagina con un SELECT + un COUNT, ``GET /sessions/{id}`` es un
    ``session.get``. El orden del listado es ``started_at DESC`` (la mas reciente
    primero); ``started_at`` siempre existe (``server_default=func.now()``).

(3) Idempotente (close). Cerrar una sesion ya cerrada es inocuo: si ``ended_at``
    ya esta seteado NO se re-setea y se devuelve 200 con el ``ended_at`` ORIGINAL
    (no 409). Solo cuando ``ended_at`` es ``None`` se asigna ``datetime.now(UTC)``.
    Asi un retry del cliente (o un doble click) no mueve el timestamp de cierre.

(4) Timestamp en Python (``datetime.now(UTC)``), NO ``func.now()``. Asignar el
    valor en Python deja el atributo poblado en la instancia ORM sin necesitar un
    ``refresh()`` tras el commit para resolver un server-default; ``SessionOut``
    se valida directo contra ``cs``. Es ademas determinista para los tests
    (asercion de no-null + monotonia / igualdad entre cierres). ``func.now()``
    complicaria el return (el valor recien existiria post-refresh).

(5) Mirror sin nada sensible. ``SessionOut`` es el mirror del modelo y no expone
    nada sensible; el wrapper de paginacion (``SessionListPage``) vive en
    ``app/schemas/session_api.py`` (no sagrado), espejando ``memory_api.py``.

(6) Rate-limit por user_id (issue #208). Las 3 rutas comparten UN bucket por
    ``user_id`` (mismo patron fail-open que ``check_chat_rate_limit`` /
    ``check_memory_export_rate_limit``): el guard 429 corre ANTES de tocar la DB,
    asi un usuario throttleado no consume conexiones del pool ni queries. fail-OPEN
    si Redis cae: ``incr_with_ttl`` => 0 => permite (baseline sin freno, nunca un
    auto-DoS). 429 con ``Retry-After`` (mismo shape que auth/chat/memory via
    ``too_many_requests``); ``detail`` neutro (regla #4).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1._http import too_many_requests
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import check_sessions_rate_limit
from app.models.session import ChatSession
from app.schemas.session import SessionOut
from app.schemas.session_api import SessionListPage
from app.workflows.consolidation import consolidate_session

logger = logging.getLogger(__name__)

router = APIRouter()

# Default + cap de la paginacion de ``GET /v1/sessions`` (igual que ``/v1/memory``).
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 100

# Detail UNICO del 404 de ``GET /sessions/{id}`` (y de ``close``): ajena e
# inexistente comparten exactamente este mensaje (sin oraculo de existencia ajena).
_NOT_FOUND_DETAIL = "sesion no encontrada"


@router.get("/sessions", response_model=SessionListPage, status_code=200)
async def list_sessions(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
    limit: Annotated[int, Query(ge=1, le=_LIMIT_MAX)] = _LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionListPage:
    """Lista las ``ChatSession`` del usuario, paginadas y ordenadas por recencia.

    - AISLAMIENTO: ``WHERE user_id == current`` en el SELECT y en el COUNT; solo
      las sesiones del user, y ``total`` es el conteo COMPLETO del user (no el
      largo de la pagina) para que el cliente pueda paginar.
    - Orden ``started_at DESC`` (la mas reciente primero). ``limit`` ∈ ``[1, 100]``
      (default 50), ``offset`` ≥ 0: FastAPI devuelve 422 fuera de rango.
    - Solo lectura: un SELECT + un COUNT, sin mutar ni encolar nada.
    - Rate-limit (decision #6): bucket por ``user_id`` compartido con get/close,
      ANTES de tocar la DB. fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.

    Returns:
        ``SessionListPage`` con ``items`` (la pagina) + ``total`` (del user).
    """
    if not await check_sessions_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().sessions_window_seconds)
    items_result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = items_result.scalars().all()

    total = await session.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    )

    return SessionListPage(
        items=[SessionOut.model_validate(cs) for cs in items],
        total=total or 0,
    )


@router.get("/sessions/{session_id}", response_model=SessionOut, status_code=200)
async def get_session(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> SessionOut:
    """Devuelve UNA ``ChatSession`` del usuario por id.

    - Busca la sesion por id. Si no existe O pertenece a otro usuario -> 404 con
      el MISMO ``detail`` (``_NOT_FOUND_DETAIL``): sin oraculo de existencia ajena,
      identico a ``close_session`` (decision #1).
    - Solo lectura: un ``session.get``, sin mutar ni encolar nada.
    - Rate-limit (decision #6): bucket por ``user_id`` compartido con list/close,
      ANTES de tocar la DB. fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.

    Returns:
        ``SessionOut`` (mirror del modelo, sin nada sensible).
    """
    if not await check_sessions_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().sessions_window_seconds)
    cs = await session.get(ChatSession, session_id)

    # Aislamiento sin oraculo: sesion inexistente y sesion ajena dan el MISMO 404.
    if cs is None or cs.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    return SessionOut.model_validate(cs)


@router.post("/sessions/{session_id}/close", response_model=SessionOut, status_code=200)
async def close_session(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> SessionOut:
    """Cierra la ``ChatSession`` del usuario seteando ``ended_at`` (idempotente).

    - Busca la sesion por id. Si no existe O pertenece a otro usuario -> 404
      (mismo error, sin oraculo de existencia ajena; ver decision #1).
    - Si ``ended_at`` ya esta seteado, NO lo cambia (idempotente, decision #2);
      devuelve 200 con el ``ended_at`` original. Si es ``None``, setea
      ``datetime.now(UTC)`` (decision #3).
    - Commitea y devuelve el ``SessionOut`` (mirror del modelo, decision #4).
    - Rate-limit (decision #6): bucket por ``user_id`` compartido con list/get,
      ANTES de tocar la DB. fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.
    - Trigger episodico (issue #209): SOLO en la rama del PRIMER cierre real
      (``ended_at`` era ``None``), DESPUES del commit, se encola
      ``consolidate_session.delay(...)``. El enqueue post-commit (igual que el de
      ``consolidate_turn`` en ``_run_chat_turn``) garantiza que el ``ended_at`` ya
      este persistido cuando el worker corra. Un segundo cierre (idempotente) NO
      re-encola: el episodio ya se disparo en el primero. Best-effort fail-open: si
      Redis esta caido, el ``.delay()`` tira y se loguea SOLO ``type(exc).__name__``
      (regla #4); el close devuelve 200 igual (la consolidacion es eventual).

    Returns:
        ``SessionOut`` con el estado de la sesion cerrada (``ended_at`` no nulo).
    """
    if not await check_sessions_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().sessions_window_seconds)
    cs = await session.get(ChatSession, session_id)

    # Aislamiento sin oraculo: sesion inexistente y sesion ajena dan el MISMO 404.
    if cs is None or cs.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    # Idempotente: solo se setea ended_at si todavia es None. Un segundo cierre
    # preserva el timestamp original (no es 409; cerrar dos veces es inocuo).
    is_first_close = cs.ended_at is None
    if is_first_close:
        cs.ended_at = datetime.now(UTC)
        # Snapshot de los primitivos ANTES del commit: el enqueue post-commit cierra
        # sobre str puros, nunca sobre atributos ORM (evita lazy-load post-commit).
        enqueue_user_id = str(cs.user_id)
        enqueue_session_id = str(cs.id)
        enqueue_mode = cs.mode.value
        await session.commit()
        await session.refresh(cs)

        # Enqueue de consolidacion episodica DESPUES del commit (M10 Ola 4), SOLO en
        # la rama del primer cierre real. fail-open: el broker caido NO rompe el
        # close (la consolidacion es eventual). .delay() es no-bloqueante.
        try:
            consolidate_session.delay(
                user_id=enqueue_user_id,
                session_id=enqueue_session_id,
                mode=enqueue_mode,
            )
        except Exception as exc:  # best-effort: el broker caido NO rompe el close.
            logger.warning("consolidate_session enqueue failed: %s", type(exc).__name__)

    return SessionOut.model_validate(cs)
