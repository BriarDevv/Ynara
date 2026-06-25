"""Derivación v1 (sin LLM) de las superficies del dashboard **Hoy** que faltaban:
``GET /v1/suggestions`` y ``GET /v1/recap``.

Hasta ahora la web las consumía contra mocks (``packages/core/.../today/api.ts``
degradaba el 404 a vacío). Acá se vuelven endpoints reales: NO inventan data ni
persisten nada — **derivan** de las tareas reales del usuario (``TaskStore``):

- ``build_suggestions``: surfacea las próximas prioridades pendientes con horario
  como nudges de preparación ("Preparate para X"). Tocarlas abre un chat para
  prepararlas (acción real, distinta de la lista de prioridades). Vacío si no hay
  nada agendado a futuro (la web oculta la sección).
- ``build_recap``: arma un borrador del día con highlights de las tareas reales
  (cerradas + pendientes). ``pending=True`` solo si hay contenido.

La **generación por LLM** (Ynara lee el día y escribe recap + sugerencias con voz
propia, roadmap F documentado en ``shared-schemas/today.ts``) es la PRÓXIMA fase;
esta v1 derivada cierra el 404 y muestra contenido real mientras tanto.

``now`` se inyecta (default ``datetime.now(UTC)``) para que los tests sean
deterministas: el "próximas" de las sugerencias y el ``date`` del recap dependen de
la hora actual.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Mode, TaskStatus
from app.schemas.today import RecapOut, SuggestionOut
from app.services.tasks import TaskStore

# Cuántos nudges de preparación surfaceamos (las próximas, no toda la agenda).
_MAX_SUGGESTIONS = 2
# Cuántas tareas cerradas listamos como highlights del recap (las más recientes
# del orden del store), para que el borrador sea conciso.
_MAX_RECAP_DONE = 3
# Namespace estable para derivar el ``id`` (uuid5) de cada sugerencia desde el id
# de su tarea: misma tarea -> mismo id de sugerencia entre requests (key de React).
_SUGGESTION_NS = uuid5(NAMESPACE_URL, "ynara:today:suggestion")


def _parse_when(iso: str) -> datetime:
    """Parsea un ``scheduled_at`` ISO a ``datetime`` aware (UTC si viene naive)."""
    when = datetime.fromisoformat(iso)
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


async def build_suggestions(
    session: AsyncSession, user_id: UUID, *, now: datetime | None = None
) -> list[SuggestionOut]:
    """Sugerencias v1: nudges de preparación de las próximas prioridades del usuario.

    Toma las tareas PENDIENTES con ``scheduled_at`` a futuro (respecto de ``now``),
    en orden de horario, y arma hasta ``_MAX_SUGGESTIONS`` sugerencias "Preparate
    para X". El ``id`` es estable por tarea (uuid5). Si no hay nada agendado a
    futuro, devuelve ``[]`` (la web oculta la sección — no se inventa contenido).

    NO usa LLM: la generación con voz propia es la próxima fase (roadmap F).
    """
    now = now or datetime.now(UTC)
    tasks = await TaskStore(session, user_id).list_tasks()

    upcoming: list[tuple[datetime, dict[str, object]]] = []
    for task in tasks:
        if task["status"] != TaskStatus.PENDING:
            continue
        scheduled_at = task["scheduled_at"]
        if not isinstance(scheduled_at, str):
            continue
        when = _parse_when(scheduled_at)
        if when > now:
            upcoming.append((when, task))

    upcoming.sort(key=lambda pair: pair[0])
    return [
        SuggestionOut(
            id=uuid5(_SUGGESTION_NS, str(task["id"])),
            title=f"Preparate para {task['title']}",
            why="Es una de tus próximas prioridades agendadas.",
            mode=Mode.PRODUCTIVIDAD,
        )
        for _when, task in upcoming[:_MAX_SUGGESTIONS]
    ]


def _recap_headline(*, done_count: int, pending_count: int) -> str:
    """Frase editorial derivada del balance del día (placeholder de la voz LLM)."""
    if done_count and not pending_count:
        return "Cerraste todo lo del día. Bien ahí."
    if done_count and pending_count:
        return "Buen avance, con algo que queda para después."
    return "El día arranca con prioridades por delante."


async def build_recap(
    session: AsyncSession, user_id: UUID, *, now: datetime | None = None
) -> RecapOut:
    """Recap v1: borrador del día derivado de las tareas reales del usuario.

    Arma highlights de las tareas cerradas ("Cerraste: X") y una línea con el
    pendiente. ``pending=True`` solo si hay contenido (highlights no vacío); si el
    usuario no tiene tareas, ``pending=False`` y la web no muestra el CTA hacia un
    recap vacío. ``headline`` es una frase derivada (la voz real es por LLM, roadmap
    F). ``date`` es ``now`` (el día del recap).
    """
    now = now or datetime.now(UTC)
    tasks = await TaskStore(session, user_id).list_tasks()

    done = [t for t in tasks if t["status"] == TaskStatus.DONE]
    pending = [t for t in tasks if t["status"] == TaskStatus.PENDING]

    highlights = [f"Cerraste: {task['title']}" for task in done[:_MAX_RECAP_DONE]]
    if pending:
        count = len(pending)
        plural = "es" if count > 1 else ""
        verb = "n" if count > 1 else ""
        highlights.append(f"Te queda{verb} {count} prioridad{plural} por hacer")

    has_content = bool(highlights)
    headline = (
        _recap_headline(done_count=len(done), pending_count=len(pending)) if has_content else None
    )
    return RecapOut(pending=has_content, date=now, headline=headline, highlights=highlights)
