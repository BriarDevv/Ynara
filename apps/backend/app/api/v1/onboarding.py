"""Onboarding del usuario: ``POST /v1/onboarding``.

Endpoint dedicado del intake de onboarding (ADR-026). En **una sola llamada
idempotente** persiste las prefs **OPERATIVAS** (``display_name`` + ``interested_modes``
+ ``a11y``) y marca ``onboarding_completed=true``. Es la identidad **PROPIA**
(``CurrentUser`` del JWT, el Bearer del draft), no un recurso ajeno.

Contrato (ADR-026 §2): lo operativo aterriza en ``users`` (``display_name`` +
``users.preferences`` JSONB); ``mood``/``mood_free_text``/``about`` son **memory-bound**
(SAGRADO, regla #3) — G4 (ADR-026 §2) los siembra en memoria semántica/procedural vía
``seed_onboarding_memory`` (best-effort, idempotente), en la MISMA transacción que lo
operativo. Sobre la tabla ``users`` (operativa, **no** sagrada — regla #3 no aplica al
endpoint; sí a la escritura en las tablas de memoria, gateada por aprobación humana).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import (
    UNAUTHORIZED_DETAIL,
    CurrentUser,
    DbSession,
    get_embedder,
    get_reranker,
)
from app.llm.clients.embedding import EmbeddingClient
from app.llm.clients.reranker import Reranker
from app.models.user import User
from app.schemas.onboarding import OnboardingIntake
from app.schemas.user import UserOut
from app.services.onboarding_seed import seed_onboarding_memory

router = APIRouter()

EmbedderDep = Annotated[EmbeddingClient, Depends(get_embedder)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


@router.post("/onboarding", response_model=UserOut, status_code=status.HTTP_200_OK)
async def complete_onboarding(
    payload: OnboardingIntake,
    session: DbSession,
    user_id: CurrentUser,
    embedder: EmbedderDep,
    reranker: RerankerDep,
) -> UserOut:
    """Persiste el intake OPERATIVO del onboarding, marca ``onboarding_completed`` y
    siembra la memoria (G4).

    - ``user_id`` sale del JWT (``CurrentUser``): 401 si el token falta / es inválido /
      expiró (lo resuelve ``get_current_user`` antes de entrar acá).
    - 401 (no 404) si el ``sub`` válido ya no tiene fila: es la identidad PROPIA caduca,
      mismo criterio que ``/v1/auth/me`` y ``PATCH /v1/users/me`` (re-autenticarse).
    - **Idempotente** (upsert natural): re-llamar (re-onboarding) PISA ``display_name`` +
      ``preferences`` y deja ``onboarding_completed=true``. El seed de memoria tampoco
      duplica (dedupe por hash + upsert por key).
    - **Sin rate-limit** (mismo criterio que ``PATCH /v1/users/me`` / ``/v1/devices``):
      write de bajo costo sobre la PROPIA fila, sin vector de enumeración ni de DoS.

    Regla #4: ``UserOut`` nunca expone ``password_hash`` (no es campo del schema).
    """
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.display_name = payload.display_name
    # OPERATIVO (ADR-026): modos de interés + a11y a ``users.preferences`` (JSONB). Se
    # serializa a tipos JSON-safe (``Mode`` -> str vía ``list(...)``; a11y vía
    # ``model_dump``) para que asyncpg lo escriba directo.
    user.preferences = {
        "interested_modes": list(payload.interested_modes),
        "a11y": payload.a11y.model_dump(),
    }
    user.onboarding_completed = True

    # G4 (ADR-026 §2): seed de memoria SAGRADA desde mood + sobre-vos, en la MISMA
    # transacción. Best-effort (savepoints por-op): si el embedder falla, NO tumba el
    # onboarding operativo. Idempotente (dedupe por hash en audit_log + upsert por key).
    await seed_onboarding_memory(
        session=session,
        user_id=user_id,
        intake=payload,
        embedder=embedder,
        reranker=reranker,
    )

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
