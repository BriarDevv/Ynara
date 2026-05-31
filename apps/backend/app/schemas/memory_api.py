"""Wrappers de respuesta de la API ``/v1/memory`` (NO sagrados).

Estos schemas son los *envelopes* del wire HTTP del endpoint read-only de la
Ola 1 (el dueño ve y exporta su propia memoria). **No** son tablas ni espejan el
modelo: solo agrupan / pagina / versionan los ``*Out`` **sagrados**
(``SemanticMemoryOut`` / ``EpisodicMemoryOut`` / ``ProceduralMemoryOut`` de
``app/schemas/memory.py``), que se reusan tal cual como ``items``.

Separación deliberada (regla #3): ``app/schemas/memory.py`` es sagrado (mirror de
las tablas cifradas) y NO se toca; los wrappers de presentación viven acá, en un
archivo nuevo que no toca el contrato de la memoria. Los ``*Out`` ya devuelven el
``content`` / ``summary`` en **plaintext** (descifrado en el store); el blob
``BYTEA`` crudo nunca entra a estos envelopes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import YnaraBaseModel
from app.schemas.memory import (
    EpisodicMemoryOut,
    ProceduralMemoryOut,
    SemanticMemoryOut,
)


class SemanticMemoryPage(YnaraBaseModel):
    """Página de hechos semánticos: los ``items`` de esta capa + el ``total`` del user."""

    items: list[SemanticMemoryOut]
    total: int


class EpisodicMemoryPage(YnaraBaseModel):
    """Página de episodios: los ``items`` de esta capa + el ``total`` del user."""

    items: list[EpisodicMemoryOut]
    total: int


class ProceduralMemoryPage(YnaraBaseModel):
    """Página de preferencias procedurales: los ``items`` + el ``total`` del user."""

    items: list[ProceduralMemoryOut]
    total: int


class MemoryGroupedResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/memory`` sin ``?layer=``: las 3 capas agrupadas.

    Cada capa es una ``*Page`` con sus ``items`` paginados (la misma página
    ``limit``/``offset`` por capa) y su ``total`` (conteo completo del user en esa
    capa). Con ``?layer=<capa>`` el endpoint devuelve la ``*Page`` de esa rama sola
    en vez de este envelope agrupado.
    """

    semantic: SemanticMemoryPage
    episodic: EpisodicMemoryPage
    procedural: ProceduralMemoryPage


class MemoryExport(YnaraBaseModel):
    """Export JSON versionado de ``GET /v1/memory/export``: las 3 capas COMPLETAS.

    Sin paginar (on-prem, pocos hechos por user). ``version`` permite evolucionar
    el formato; ``exported_at`` es ``datetime.now(UTC)`` del momento del export.
    El contenido va descifrado (los ``*Out`` traen ``content`` / ``summary`` en
    plaintext); el blob cifrado nunca viaja.
    """

    version: int
    exported_at: datetime
    semantic: list[SemanticMemoryOut]
    episodic: list[EpisodicMemoryOut]
    procedural: list[ProceduralMemoryOut]


class MemoryPatchRequest(YnaraBaseModel):
    """Body de ``PATCH /v1/memory/{layer}/{ref}`` (NO sagrado, envelope del wire).

    Polimórfico por capa, pero **no** se mete en ``schemas/memory.py`` (sagrado):
    el contrato de la mutación individual es de presentación, no espeja una tabla.
    Ambos campos son opcionales acá porque el body válido depende del ``layer`` del
    path (que el schema no conoce); el endpoint valida la correspondencia y devuelve
    422 si el body no aplica a la capa:

    - ``semantic``: requiere ``content`` (str no vacío) → re-embeddea + re-cifra.
    - ``procedural``: requiere ``value`` (dict) → reemplaza el JSONB de una key
      EXISTENTE.
    - ``episodic``: no admite PATCH (405); este body nunca se evalúa para esa capa.

    ``content`` replica el ``min_length=1`` del ``SemanticMemoryCreate`` sagrado
    (FastAPI da 422 si llega ``""``); ``value`` es un dict arbitrario (JSONB).
    """

    content: str | None = Field(default=None, min_length=1, max_length=4096)
    value: dict[str, Any] | None = None
