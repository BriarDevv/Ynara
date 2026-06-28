"""Schemas del dashboard **Hoy** que aún no tenían backend: sugerencias + recap.

Espejo Pydantic del contrato del wire (``packages/shared-schemas/src/today.ts``,
``SuggestionSchema`` / ``SuggestionsResponseSchema`` / ``RecapSchema``): "Pydantic
gana, Zod sigue". Las prioridades del día (``/v1/tasks``) ya viven en
``app/schemas/task.py`` + ``task_api.py``; acá se completan las DOS superficies
que la web consumía contra mocks (``/v1/suggestions`` y ``/v1/recap``).

NO sagrado, NO es una tabla: estas respuestas se DERIVAN de las tareas del usuario
(``app/services/today.py``) —y ``suggestions`` además de sus prefs + memoria sembrada
para el cold-start (G5)—, no se persisten. La generación por LLM real (que la web
documenta como roadmap F) es la próxima fase; esta es la v1 derivada.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.enums import Mode
from app.schemas.base import YnaraBaseModel


class SuggestionOut(YnaraBaseModel):
    """Una sugerencia proactiva ("Ynara sugiere"). Espeja ``SuggestionSchema``.

    ``why`` es el "porqué" que la vuelve honesta (no una orden arbitraria); ``mode``
    la tiñe y la asocia a un modo, o ``None`` si es transversal. ``id`` es estable
    por sugerencia (la web lo usa como key de React): el servicio lo deriva
    determinísticamente del origen, no es aleatorio por request.
    """

    id: UUID
    title: str = Field(min_length=1)
    why: str = Field(min_length=1)
    mode: Mode | None


class SuggestionsResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/suggestions``. Espeja ``SuggestionsResponseSchema``.

    ``items`` vacío es válido y esperado (la web oculta la sección si no hay
    sugerencias): no se inventa contenido cuando no hay señal real.
    """

    items: list[SuggestionOut]


class RecapOut(YnaraBaseModel):
    """Recap del día. Espeja ``RecapSchema`` (wireframe 15, CTA del 06).

    - ``pending``: ``True`` cuando hay un borrador con contenido para mostrar (la web
      muestra el CTA "Recap pendiente" solo si ``pending``). En esta v1 sin
      mecanismo de cierre del día, ``pending`` modela "hay algo que recapitular":
      ``True`` si ``highlights`` no está vacío, ``False`` si no hubo actividad (así
      un usuario sin tareas no ve un CTA hacia un recap vacío).
    - ``date``: el día al que pertenece el recap (ISO con offset).
    - ``headline``: frase editorial de cierre. La generación real es por LLM (roadmap
      F); la v1 derivada arma una frase simple según la actividad, o ``None`` si no
      hay nada.
    - ``highlights``: lo más importante del día, en bullets, derivado de las tareas
      reales del usuario.
    """

    pending: bool
    date: datetime
    headline: str | None
    highlights: list[str]
