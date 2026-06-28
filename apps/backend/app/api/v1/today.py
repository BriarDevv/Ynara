"""Lecturas derivadas del dashboard **Hoy**: ``GET /v1/suggestions`` + ``GET /v1/recap``.

Completa las dos superficies que la web consumía contra mocks (las prioridades
``/v1/tasks`` ya eran reales). No hay tabla ni persistencia: se DERIVAN de las tareas
reales del usuario (``app/services/today.py``); ``suggestions`` además rellena el
cold-start con prefs + memoria sembrada (G5). La generación por LLM real es la próxima
fase (roadmap F, ver ``shared-schemas/today.ts``).

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
from app.llm.prompts.datetime_context import APP_TIMEZONE
from app.models.user import User
from app.schemas.today import RecapOut, SuggestionsResponse
from app.services.today import build_recap, build_suggestions

router = APIRouter()


async def _resolve_user_tz(session: DbSession, user_id: CurrentUser) -> str:
    """Huso del usuario (``users.time_zone``) para computar su "hoy"; default app si falta.

    El recap/sugerencias derivan el "hoy" en el huso del usuario (no UTC): un usuario en
    Buenos Aires ve el recap de SU día. Si la fila no se resuelve (caso raro), cae a
    ``APP_TIMEZONE`` (back-compat).
    """
    user = await session.get(User, user_id)
    return user.time_zone if user is not None else APP_TIMEZONE


@router.get("/suggestions", response_model=SuggestionsResponse, status_code=200)
async def get_suggestions(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> SuggestionsResponse:
    """Sugerencias proactivas ("Ynara sugiere") derivadas de las tareas + el perfil.

    - AISLAMIENTO: ``build_suggestions`` deriva del ``TaskStore`` ligado al ``user_id``
      del JWT; solo ve las tareas del usuario.
    - COLD-START (G5): si faltan nudges de tareas, rellena con nudges de arranque por
      modo, de los ``interested_modes`` (prefs) ordenados por la dedicación sembrada
      (memoria procedural) — primeras recomendaciones aunque el usuario no tenga tasks.
    - Rate-limit: bucket por ``user_id`` del dashboard Hoy, ANTES de tocar la DB.
      fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.
    - ``items`` vacío es válido (la web oculta la sección): no se inventa contenido.

    Returns:
        ``SuggestionsResponse`` con ``items`` (las sugerencias derivadas).
    """
    if not await check_tasks_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().tasks_window_seconds)

    tz = await _resolve_user_tz(session, user_id)
    items = await build_suggestions(session, user_id, tz=tz)
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

    tz = await _resolve_user_tz(session, user_id)
    return await build_recap(session, user_id, tz=tz)
