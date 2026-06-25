"""Lecturas derivadas del dashboard **Hoy**: ``GET /v1/suggestions`` + ``GET /v1/recap``.

Completa las dos superficies que la web consumía contra mocks (las prioridades
``/v1/tasks`` ya eran reales). No hay tabla ni persistencia: ambas se DERIVAN de las
tareas reales del usuario (``app/services/today.py``); la generación por LLM real es
la próxima fase (roadmap F, ver ``shared-schemas/today.ts``).

Mismo aislamiento + rate-limit que ``/v1/tasks`` (son parte del MISMO dashboard, que
ya carga ``/tasks``): el ``user_id`` sale del JWT (``CurrentUser``) y todo query
filtra por él; el guard 429 corre ANTES de tocar la DB (fail-open si Redis cae),
compartiendo el bucket por ``user_id`` del dashboard Hoy. Solo lectura, sin commit.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1._http import too_many_requests
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import check_tasks_rate_limit
from app.schemas.today import RecapOut, SuggestionsResponse
from app.services.today import build_recap, build_suggestions

router = APIRouter()


@router.get("/suggestions", response_model=SuggestionsResponse, status_code=200)
async def get_suggestions(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> SuggestionsResponse:
    """Sugerencias proactivas ("Ynara sugiere") derivadas de las tareas del usuario.

    - AISLAMIENTO: ``build_suggestions`` deriva del ``TaskStore`` ligado al ``user_id``
      del JWT; solo ve las tareas del usuario.
    - Rate-limit: bucket por ``user_id`` del dashboard Hoy, ANTES de tocar la DB.
      fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.
    - ``items`` vacío es válido (la web oculta la sección): no se inventa contenido.

    Returns:
        ``SuggestionsResponse`` con ``items`` (las sugerencias derivadas).
    """
    if not await check_tasks_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().tasks_window_seconds)

    items = await build_suggestions(session, user_id)
    return SuggestionsResponse(items=items)


@router.get("/recap", response_model=RecapOut, status_code=200)
async def get_recap(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> RecapOut:
    """Recap del día (borrador derivado de las tareas reales del usuario).

    - AISLAMIENTO: ``build_recap`` deriva del ``TaskStore`` ligado al ``user_id``.
    - Rate-limit: mismo bucket del dashboard Hoy, ANTES de tocar la DB. fail-open.
    - ``pending=False`` cuando no hay nada que recapitular (la web oculta el CTA).

    Returns:
        ``RecapOut`` con ``pending`` / ``date`` / ``headline`` / ``highlights``.
    """
    if not await check_tasks_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().tasks_window_seconds)

    return await build_recap(session, user_id)
