"""Helper de ciclo de vida de ChatSession para el endpoint /v1/chat.

``resolve_chat_session`` resuelve (crea o valida) la sesión activa del
usuario antes de invocar el router LLM. NO commitea: el commit lo hace el
endpoint al final del request, después de que route() devuelve (fix del
bug de commit-temprano documentado en las decisiones de diseño M9).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode
from app.models.session import ChatSession


async def resolve_chat_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID | None,
    mode: Mode,
) -> ChatSession:
    """Crea o valida la ChatSession del usuario para el turno de chat.

    - ``session_id`` es ``None`` → crea una nueva ChatSession, hace
      ``flush()`` para que el ORM asigne el id (sin commit; el commit lo
      hace el endpoint al final del request).
    - ``session_id`` presente → busca la sesión; lanza 404 si no existe o
      pertenece a otro usuario (sin dar oráculo de existencia ajena), 409
      si el modo no coincide con el de la sesión abierta.

    No propaga errores del ORM; si hay un problema de infraestructura el
    ``get_db()`` wrapper hace rollback.
    """
    if session_id is None:
        cs = ChatSession(user_id=user_id, mode=mode)
        session.add(cs)
        await session.flush()
        return cs

    cs = await session.get(ChatSession, session_id)

    if cs is None or cs.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="sesion no encontrada",
        )

    if cs.mode != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no se puede cambiar de modo en una sesion abierta",
        )

    return cs
