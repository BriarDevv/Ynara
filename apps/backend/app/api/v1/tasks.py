"""CRUD del dominio **TAREAS** (Fase D1, espejo de Agenda/ADR-018): ``GET`` /
``PATCH`` sobre ``/v1/tasks``.

El dashboard "Hoy" de la web ya consume estos endpoints contra mocks
(``packages/core/src/features/today/api.ts``); acá se vuelven reales. El contrato
del wire vive en ``packages/shared-schemas/src/today.ts`` y lo espejan los schemas
``app/schemas/task.py`` ("Pydantic gana, Zod sigue"). El alta de tareas la hace el
**agente** por detrás de la conversación (``task.create_task``, ver
``app/llm/tools/task.py`` + ``app/workflows/agent_pass.py``): por eso el CRUD HTTP
expone solo lectura + toggle de estado, no un ``POST`` manual (el front no crea
tareas a mano; las extrae el agente).

Las 2 rutas comparten el MISMO aislamiento por usuario: el ``user_id`` sale del JWT
(``CurrentUser``) y todo query filtra por él. El ``PATCH`` commitea.

Decisiones de diseño (mismas que ``events.py`` / ``sessions.py``, NO re-litigar):

(1) Aislamiento sin oráculo. Una tarea inexistente y una tarea de otro usuario dan
    el MISMO 404 (mismo status + mismo ``detail``) en ``PATCH``; nunca se revela la
    existencia de una tarea ajena. El ``GET /tasks`` lista SOLO las del user
    (``WHERE user_id == current``) y su ``total`` es el conteo del user.

(2) Orden sensato: pending primero (lo que falta hacer), luego por ``scheduled_at``
    ASC (la próxima primero; las sin horario al final). Lo resuelve el store.

(3) ``status`` arranca ``pending`` en el alta (que la hace el agente, no este router).
    El ``PATCH`` togglea entre ``pending``/``done`` (el front manda el opuesto).

(4) Rate-limit por user_id ANTES de tocar la DB (fail-open). Las 2 rutas comparten
    UN bucket por ``user_id`` (mismo patrón que ``/v1/events``): el guard 429 corre
    ANTES de cualquier query, así un usuario throttleado no consume conexiones del
    pool. fail-OPEN si Redis cae (``incr_with_ttl`` => 0 => permite). 429 con
    ``Retry-After`` + ``detail`` neutro (regla #4).

(5) Mirror sin nada de más. ``TaskOut`` NO expone ``user_id`` / ``created_at`` /
    ``updated_at`` (el contrato del front no los declara); el envelope
    ``TasksResponse`` (``items`` + ``total``) vive en ``app/schemas/task_api.py``
    (no sagrado). El ``PATCH`` devuelve el ``TaskOut`` SOLO (no el envelope), igual
    que ``useToggleTask()`` lo valida con ``TaskSchema.parse``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.v1._http import too_many_requests
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, TokenStoreDep
from app.core.ratelimit import check_tasks_rate_limit
from app.models.task import Task
from app.schemas.task import TaskOut, TaskPatch
from app.schemas.task_api import TasksResponse
from app.tasks.store import TaskStore

router = APIRouter()

# Detail ÚNICO del 404 del ``PATCH``: ajena e inexistente comparten exactamente este
# mensaje (sin oráculo de existencia ajena).
_NOT_FOUND_DETAIL = "tarea no encontrada"


@router.get("/tasks", response_model=TasksResponse, status_code=200)
async def list_tasks(
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> TasksResponse:
    """Lista las tareas del usuario, pending primero y luego por ``scheduled_at`` ASC.

    - AISLAMIENTO: ``WHERE user_id == current`` en el SELECT (vía ``TaskStore``) y en
      el COUNT; solo las tareas del user, y ``total`` es el conteo COMPLETO del user.
    - Orden (decisión #2): pending arriba, luego por horario ASC (lo resuelve el store).
    - Solo lectura: un SELECT (vía store) + un COUNT, sin mutar nada.
    - Rate-limit (decisión #4): bucket por ``user_id`` compartido con las 2 rutas,
      ANTES de tocar la DB. fail-open si Redis cae. 429 + ``Retry-After`` al cruzar.

    Returns:
        ``TasksResponse`` con ``items`` (las tareas del user) + ``total``.
    """
    if not await check_tasks_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().tasks_window_seconds)

    items = await TaskStore(session, user_id).list_tasks()

    total = await session.scalar(
        select(func.count()).select_from(Task).where(Task.user_id == user_id)
    )

    # ``list_tasks`` devuelve dicts JSON-safe (``_to_result`` => ``model_dump(mode="json")``:
    # id/status/scheduled_at como str), porque el MISMO store alimenta el tool loop del
    # agente, que serializa con ``json.dumps``. Re-validar esos dicts del wire bajo el
    # ``strict=True`` heredado de ``YnaraBaseModel`` los rechazaría (un ``str`` no es
    # instancia de ``UUID``/``TaskStatus``/``datetime``), así que se re-hidratan con
    # ``strict=False`` —MISMO criterio que los schemas de request, que parsean JSON del
    # wire sin strict—. El round-trip es lossless (los dicts ya son un ``TaskOut`` válido)
    # y las instancias resultantes traen tipos reales, así que la revalidación strict de
    # FastAPI sobre ``response_model`` (lee atributos nativos) las acepta.
    return TasksResponse(
        items=[TaskOut.model_validate(item, strict=False) for item in items],
        total=total or 0,
    )


@router.patch("/tasks/{task_id}", response_model=TaskOut, status_code=200)
async def patch_task(
    task_id: UUID,
    payload: TaskPatch,
    session: DbSession,
    user_id: CurrentUser,
    store: TokenStoreDep,
) -> TaskOut:
    """Togglea el ``status`` de una tarea del usuario y devuelve el ``TaskOut``.

    - Busca la tarea por id (vía ``TaskStore``, que filtra por ``user_id``). Si no
      existe O pertenece a otro usuario -> 404 con el MISMO ``detail`` (sin oráculo de
      existencia ajena, decisión #1).
    - Fija el ``status`` enviado (el front manda el opuesto al actual: el toggle del
      check). El ``PATCH`` no toca otros campos (es el toggle mínimo del wireframe).
    - Rate-limit (decisión #4): ANTES de tocar la DB. fail-open si Redis cae.
    - Commitea y devuelve la tarea actualizada (el ``TaskOut`` SOLO, decisión #5).

    Returns:
        ``TaskOut`` de la tarea actualizada.
    """
    if not await check_tasks_rate_limit(store, user_id=str(user_id)):
        raise too_many_requests(get_settings().tasks_window_seconds)

    updated = await TaskStore(session, user_id).set_status(task_id, payload.status)

    # Aislamiento sin oráculo: tarea inexistente y tarea ajena dan el MISMO 404.
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )

    await session.commit()

    # ``set_status`` devuelve un dict JSON-safe (mismo ``_to_result`` que ``list_tasks``);
    # se re-hidrata con ``strict=False`` por la misma razón (ver ``list_tasks``).
    return TaskOut.model_validate(updated, strict=False)
