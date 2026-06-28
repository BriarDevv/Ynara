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

from app.enums import Mode
from app.memory.procedural import ProceduralMemoryStore
from app.models.user import User
from app.schemas.today import RecapOut, SuggestionOut
from app.services.onboarding_seed import DEDICATION_KEY
from app.services.tasks import TaskStore

# Cuántos nudges de preparación surfaceamos (las próximas, no toda la agenda).
_MAX_SUGGESTIONS = 2
# Cuántas tareas cerradas listamos como highlights del recap (las más recientes),
# para que el borrador sea conciso.
_MAX_RECAP_DONE = 3
# Namespace estable para derivar el ``id`` (uuid5) de cada sugerencia desde el id
# de su tarea: misma tarea -> mismo id de sugerencia entre requests (key de React).
_SUGGESTION_NS = uuid5(NAMESPACE_URL, "ynara:today:suggestion")

# Nudges de arranque por modo (G5, ADR-026): copy fiel a los descriptores canónicos
# (``@ynara/core/features/modes``). ``why`` honesto — referencia que el usuario lo
# eligió en el onboarding (no es una orden arbitraria).
_MODE_NUDGE: dict[Mode, tuple[str, str]] = {
    Mode.PRODUCTIVIDAD: (
        "Organizá tu día con Productividad",
        "Lo elegiste para agendar, recordar y ejecutar.",
    ),
    Mode.ESTUDIO: (
        "Arrancá una sesión de Estudio",
        "Lo elegiste para que te explique y te acompañe a estudiar.",
    ),
    Mode.BIENESTAR: (
        "Date un momento en Bienestar",
        "Lo elegiste para descargar y que te acompañe.",
    ),
    Mode.VIDA: (
        "Charlá un rato en Vida",
        "Lo elegiste para charlas casuales y recomendaciones.",
    ),
    Mode.MEMORIA: (
        "Mirá lo que Ynara va recordando",
        "Lo elegiste para no perder el hilo de tus charlas.",
    ),
}

# Exhaustividad: cada modo del enum debe tener su nudge. Un modo nuevo sin copy es un
# bug (daría KeyError en el cold-start); esto lo caza al importar, no en runtime.
assert set(_MODE_NUDGE) == set(Mode), "falta el nudge de cold-start de algún Mode"

# Dedicación sembrada (memoria procedural) -> modo(s) que se priorizan en el cold-start.
# "otro"/ausente: sin preferencia (se respeta el orden de ``interested_modes``).
_DEDICATION_PREFERRED_MODES: dict[str, tuple[Mode, ...]] = {
    "estudio": (Mode.ESTUDIO,),
    "trabajo": (Mode.PRODUCTIVIDAD,),
    "ambos": (Mode.ESTUDIO, Mode.PRODUCTIVIDAD),
}

# Valores válidos del enum ``Mode`` para parsear ``interested_modes`` (JSONB) defensivamente.
_MODE_VALUES: frozenset[str] = frozenset(m.value for m in Mode)


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
    """Sugerencias v1: nudges de preparación de tareas + relleno de cold-start por modo.

    Primero toma (vía SQL acotado) las tareas PENDIENTES con ``scheduled_at`` a futuro
    respecto de ``now``, en orden de horario, hasta ``_MAX_SUGGESTIONS``, y arma una
    sugerencia "Preparate para X" por cada una (``mode=None`` transversal; ``id`` estable
    por tarea). Si quedan slots (pocas/ninguna tarea agendada), los **rellena con nudges
    de arranque por modo** derivados de los modos elegidos en el onboarding
    (``users.preferences.interested_modes``) y ordenados por la dedicación sembrada
    (memoria procedural) — G5/ADR-026: primeras recomendaciones aunque no haya tasks. Si
    el usuario no tiene tareas a futuro NI modos (fila pre-onboarding), devuelve ``[]``.

    NO usa LLM: la generación con voz propia es la próxima fase (roadmap F).
    """
    now = _local_now(now, tz)
    upcoming = await TaskStore(session, user_id).list_upcoming_pending(
        after=now, limit=_MAX_SUGGESTIONS
    )
    suggestions = [
        SuggestionOut(
            id=uuid5(_SUGGESTION_NS, str(task["id"])),
            title=f"Preparate para {task['title']}",
            why="Es una de tus próximas prioridades agendadas.",
            mode=None,
        )
        for task in upcoming
    ]

    remaining = _MAX_SUGGESTIONS - len(suggestions)
    if remaining > 0:
        suggestions.extend(await _mode_suggestions(session, user_id, limit=remaining))
    return suggestions


async def _read_dedication(session: AsyncSession, user_id: UUID) -> str | None:
    """Dedicación sembrada (memoria procedural) para ordenar los nudges de modo.

    Lee la entrada ``onboarding.dedication`` del ``ProceduralMemoryStore``; no descifra
    nada (procedural es JSONB plano). ``None`` si el usuario no la sembró (saltó el step).
    """
    entry = await ProceduralMemoryStore(session, user_id).get(DEDICATION_KEY)
    if entry is None:
        return None
    value = entry.value.get("dedication")
    return value if isinstance(value, str) else None


async def _mode_suggestions(
    session: AsyncSession, user_id: UUID, *, limit: int
) -> list[SuggestionOut]:
    """Nudges de arranque por modo para el cold-start (G5, ADR-026).

    Deriva de los modos que el usuario eligió en el onboarding
    (``users.preferences.interested_modes``, prefs operativas) y los ordena poniendo
    primero el que matchea su dedicación sembrada (memoria procedural). ``why`` honesto
    (lo eligió él); ``mode`` seteado para el tint; ``id`` estable por modo. Devuelve hasta
    ``limit``; ``[]`` si el usuario no tiene modos (fila pre-onboarding).
    """
    user = await session.get(User, user_id)
    if user is None:
        return []
    raw_modes = (user.preferences or {}).get("interested_modes", [])
    modes = [Mode(m) for m in raw_modes if isinstance(m, str) and m in _MODE_VALUES]
    if not modes:
        return []

    dedication = await _read_dedication(session, user_id)
    preferred = _DEDICATION_PREFERRED_MODES.get(dedication or "", ())
    # Orden estable: primero los modos que matchean la dedicación sembrada (los demás
    # conservan el orden en que el usuario los eligió).
    modes.sort(key=lambda m: 0 if m in preferred else 1)

    out: list[SuggestionOut] = []
    seen: set[Mode] = set()
    for mode in modes:
        if len(out) >= limit:
            break
        if mode in seen:
            continue
        seen.add(mode)
        title, why = _MODE_NUDGE[mode]
        out.append(
            SuggestionOut(
                id=uuid5(_SUGGESTION_NS, f"mode:{mode.value}"),
                title=title,
                why=why,
                mode=mode,
            )
        )
    return out


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
