"""Derivación v1 (sin LLM) de las superficies del dashboard **Hoy** que faltaban:
``GET /v1/suggestions`` y ``GET /v1/recap``.

Hasta ahora la web las consumía contra mocks (``packages/core/.../today/api.ts``
degradaba el 404 a vacío). Acá se vuelven endpoints reales: NO inventan data ni
persisten nada — **derivan** de las tareas reales del usuario (``TaskStore``), con
queries ACOTADAS en SQL (``list_upcoming_pending`` / ``list_recent_done`` /
``count_pending``: no traen toda la tabla, evitando la regresión de API-002 en el
camino caliente del dashboard):

- ``build_suggestions``: surfacea las próximas prioridades pendientes con horario
  como nudges de preparación ("Preparate para X"). Tocarlas abre un chat para
  prepararlas (acción real, distinta de la lista de prioridades). Vacío si no hay
  nada agendado a futuro (la web oculta la sección). ``mode=None`` (transversal): la
  v1 no puede derivar el modo real de la tarea, y un valor fijo incorrecto teñiría
  mal; ``None`` es lo que el wire/Zod aceptan como "transversal".
- ``build_recap``: arma un borrador del día con highlights de las tareas reales
  (cerradas + el conteo de pendientes). ``pending=True`` solo si hay contenido.

La **generación por LLM** (Ynara lee el día y escribe recap + sugerencias con voz
propia, roadmap F documentado en ``shared-schemas/today.ts``) es la PRÓXIMA fase;
esta v1 derivada cierra el 404 y muestra contenido real mientras tanto.

``now`` se inyecta (default ``datetime.now(UTC)``) para que los tests sean
deterministas. Se normaliza a aware (UTC si viene naive) para no romper la
comparación con ``scheduled_at`` (que es ``timestamptz``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.today import RecapOut, SuggestionOut
from app.services.tasks import TaskStore

# Cuántos nudges de preparación surfaceamos (las próximas, no toda la agenda).
_MAX_SUGGESTIONS = 2
# Cuántas tareas cerradas listamos como highlights del recap (las más recientes),
# para que el borrador sea conciso.
_MAX_RECAP_DONE = 3
# Namespace estable para derivar el ``id`` (uuid5) de cada sugerencia desde el id
# de su tarea: misma tarea -> mismo id de sugerencia entre requests (key de React).
_SUGGESTION_NS = uuid5(NAMESPACE_URL, "ynara:today:suggestion")


def _local_now(now: datetime | None, tz: str) -> datetime:
    """``now`` normalizado a timezone-aware y expresado en el huso ``tz`` del usuario.

    Default UTC (``datetime.now(UTC)``) y, si viene naive, se asume UTC; luego se convierte
    al huso del usuario (``astimezone``). Convertir NO cambia el instante absoluto (la
    comparación con ``scheduled_at`` sigue siendo correcta), pero deja ``date`` y el "hoy"
    expresados en el wall-clock del usuario. Con ``tz='UTC'`` (default) es idéntico al
    comportamiento previo (instante UTC), así no rompe a los callers que no pasan ``tz``.
    """
    base = datetime.now(UTC) if now is None else now
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base.astimezone(ZoneInfo(tz))


async def build_suggestions(
    session: AsyncSession, user_id: UUID, *, now: datetime | None = None, tz: str = "UTC"
) -> list[SuggestionOut]:
    """Sugerencias v1: nudges de preparación de las próximas prioridades del usuario.

    Toma (vía SQL acotado) las tareas PENDIENTES con ``scheduled_at`` a futuro
    respecto de ``now``, en orden de horario, hasta ``_MAX_SUGGESTIONS``, y arma una
    sugerencia "Preparate para X" por cada una. El ``id`` es estable por tarea
    (uuid5). ``mode=None`` (transversal): la v1 no deriva el modo real. Si no hay
    nada agendado a futuro, devuelve ``[]`` (la web oculta la sección).

    NO usa LLM: la generación con voz propia es la próxima fase (roadmap F).
    """
    now = _local_now(now, tz)
    upcoming = await TaskStore(session, user_id).list_upcoming_pending(
        after=now, limit=_MAX_SUGGESTIONS
    )
    return [
        SuggestionOut(
            id=uuid5(_SUGGESTION_NS, str(task["id"])),
            title=f"Preparate para {task['title']}",
            why="Es una de tus próximas prioridades agendadas.",
            mode=None,
        )
        for task in upcoming
    ]


def _recap_headline(*, done_count: int, pending_count: int) -> str:
    """Frase editorial derivada del balance del día (placeholder de la voz LLM)."""
    if done_count and not pending_count:
        return "Cerraste todo lo del día. Bien ahí."
    if done_count and pending_count:
        return "Buen avance, con algo que queda para después."
    return "El día arranca con prioridades por delante."


async def build_recap(
    session: AsyncSession, user_id: UUID, *, now: datetime | None = None, tz: str = "UTC"
) -> RecapOut:
    """Recap v1: borrador del día derivado de las tareas reales del usuario.

    Arma highlights de las tareas cerradas recientes ("Cerraste: X", vía SQL acotado)
    y una línea con el conteo de pendientes. ``pending=True`` solo si hay contenido;
    si el usuario no tiene tareas, ``pending=False`` y la web no muestra el CTA hacia
    un recap vacío. ``headline`` es una frase derivada (la voz real es por LLM,
    roadmap F). ``date`` es ``now`` expresado en el huso ``tz`` del usuario (el día del
    recap es el de SU calendario, no el de UTC).
    """
    now = _local_now(now, tz)
    store = TaskStore(session, user_id)
    done = await store.list_recent_done(limit=_MAX_RECAP_DONE)
    pending_count = await store.count_pending()

    highlights = [f"Cerraste: {task['title']}" for task in done]
    if pending_count:
        plural = "es" if pending_count > 1 else ""
        verb = "n" if pending_count > 1 else ""
        highlights.append(f"Te queda{verb} {pending_count} prioridad{plural} por hacer")

    # Únicos preservando orden: dos tareas cerradas con el MISMO título no duplican
    # la línea (ni la key de React del front, que usa el string como key).
    highlights = list(dict.fromkeys(highlights))

    has_content = bool(highlights)
    headline = (
        _recap_headline(done_count=len(done), pending_count=pending_count) if has_content else None
    )
    return RecapOut(pending=has_content, date=now, headline=headline, highlights=highlights)
