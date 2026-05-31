"""Endpoint HTTP de ciclo de vida de sesion: ``POST /v1/sessions/{id}/close``.

Cierra una ``ChatSession`` seteando ``ended_at``. Es el trigger de cierre que
mas adelante (M10 Ola 4) dispara la consolidacion episodica; aca entrega SOLO el
lifecycle (setear ``ended_at``), sin tocar memoria ni encolar nada.

Decisiones de diseno (criticadas, NO re-litigar):

(1) Aislamiento por usuario, sin oraculo. El ``user_id`` sale del JWT
    (``CurrentUser``). Una sesion inexistente y una sesion de otro usuario dan el
    MISMO 404 (mismo status + mismo ``detail``); nunca se revela la existencia de
    una sesion ajena. Identico al patron de ``resolve_chat_session`` en
    ``app/api/v1/_sessions.py``.

(2) Idempotente. Cerrar una sesion ya cerrada es inocuo: si ``ended_at`` ya esta
    seteado NO se re-setea y se devuelve 200 con el ``ended_at`` ORIGINAL (no
    409). Solo cuando ``ended_at`` es ``None`` se asigna ``datetime.now(UTC)``.
    Asi un retry del cliente (o un doble click) no mueve el timestamp de cierre.

(3) Timestamp en Python (``datetime.now(UTC)``), NO ``func.now()``. Asignar el
    valor en Python deja el atributo poblado en la instancia ORM sin necesitar un
    ``refresh()`` tras el commit para resolver un server-default; ``SessionOut``
    se valida directo contra ``cs``. Es ademas determinista para los tests
    (asercion de no-null + monotonia / igualdad entre cierres). ``func.now()``
    complicaria el return (el valor recien existiria post-refresh).

(4) Solo lifecycle. El endpoint setea ``ended_at`` y commitea: NO toca memoria,
    NO encola consolidacion (la episodica es M10 Ola 4). ``SessionOut`` es el
    mirror del modelo y no expone nada sensible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.models.session import ChatSession
from app.schemas.session import SessionOut

router = APIRouter()


@router.post("/sessions/{session_id}/close", response_model=SessionOut, status_code=200)
async def close_session(
    session_id: UUID,
    session: DbSession,
    user_id: CurrentUser,
) -> SessionOut:
    """Cierra la ``ChatSession`` del usuario seteando ``ended_at`` (idempotente).

    - Busca la sesion por id. Si no existe O pertenece a otro usuario -> 404
      (mismo error, sin oraculo de existencia ajena; ver decision #1).
    - Si ``ended_at`` ya esta seteado, NO lo cambia (idempotente, decision #2);
      devuelve 200 con el ``ended_at`` original. Si es ``None``, setea
      ``datetime.now(UTC)`` (decision #3).
    - Commitea y devuelve el ``SessionOut`` (mirror del modelo, decision #4).

    Returns:
        ``SessionOut`` con el estado de la sesion cerrada (``ended_at`` no nulo).
    """
    cs = await session.get(ChatSession, session_id)

    # Aislamiento sin oraculo: sesion inexistente y sesion ajena dan el MISMO 404.
    if cs is None or cs.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="sesion no encontrada",
        )

    # Idempotente: solo se setea ended_at si todavia es None. Un segundo cierre
    # preserva el timestamp original (no es 409; cerrar dos veces es inocuo).
    if cs.ended_at is None:
        cs.ended_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(cs)

    return SessionOut.model_validate(cs)
