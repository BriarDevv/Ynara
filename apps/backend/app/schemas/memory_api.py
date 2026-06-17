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

from app.enums import MemoryLayer
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


class MemoryWipePreview(YnaraBaseModel):
    """Dry-run de ``POST /v1/memory/wipe?dry_run=true``: conteos por capa de lo que se borraría.

    Read-only: el endpoint cuenta las 3 capas del user (``count()`` por store) y arma este
    preview. ``total`` es la suma de las 3 capas. **Solo enteros** (regla #4): NUNCA un campo
    ``content`` / ``summary`` — el dry-run no descifra ni proyecta contenido, solo conteos.
    Siempre 200, incluso todo en 0 (un user sin memoria es estado válido; jamás 404).
    """

    semantic: int
    episodic: int
    procedural: int
    total: int


class MemoryWipeConfirm(YnaraBaseModel):
    """Body de ``POST /v1/memory/wipe``: el confirm per-layer (guarda de intención).

    El cliente manda los conteos por capa que vio en el preview fresco. El execute reconcuenta
    las 3 capas y, si ``(semantic, episodic, procedural)`` actuales **no** coinciden con estos
    ``expected_*``, devuelve **409** con los conteos ACTUALES (para que el cliente re-confirme
    con un preview fresco) sin borrar nada. Es una guarda de INTENCIÓN (prueba que el humano
    vio el plan), no cirugía exacta: si coinciden, el ``DELETE WHERE user_id`` barre el estado
    presente completo y el receipt reporta el rowcount REAL.

    Cada campo es ``ge=0`` (un conteo nunca es negativo). ``extra=forbid`` (heredado de
    ``YnaraBaseModel``): un campo de más → 422.
    """

    expected_semantic: int = Field(ge=0)
    expected_episodic: int = Field(ge=0)
    expected_procedural: int = Field(ge=0)


class MemoryWipeResult(YnaraBaseModel):
    """Receipt de ``POST /v1/memory/wipe`` exitoso: conteos REALMENTE borrados por capa.

    Gemelo de ``MemoryWipePreview`` pero con un nombre distinto a propósito: que no haya
    ambigüedad sobre si ya se borró (``Result``) o si es el dry-run (``Preview``). Cada campo
    es el ``rowcount`` REAL del ``wipe()`` de esa capa (lo que el ``DELETE`` borró de verdad,
    que puede diferir del preview si el worker insertó en el ínterin). ``total`` = suma de las
    3 capas. **Solo enteros** (regla #4): NUNCA ``content`` / ``summary``.
    """

    semantic: int
    episodic: int
    procedural: int
    total: int


class MemorySearchHit(YnaraBaseModel):
    """Un resultado de ``GET /v1/memory/search`` (NO sagrado, envelope del wire).

    ``ref`` es el UUID (semantic/episodic); ``snippet`` es el ``content`` /
    ``summary`` ya **descifrado** por el store (el blob cifrado nunca viaja);
    ``occurred_at`` es cuándo ocurrió/se creó. ``score`` es un proxy de relevancia
    0..1 derivado del **RANK**: el reranker del store no expone su score crudo y la
    firma sagrada (``app/memory/``) no se toca (regla #3), pero el store ya
    devuelve los resultados **ordenados por relevancia**, así que esa posición se
    codifica como score decreciente (mismo decaimiento que el mock del front).
    """

    layer: MemoryLayer
    ref: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)
    occurred_at: datetime | None


class MemorySearchResponse(YnaraBaseModel):
    """Respuesta de ``GET /v1/memory/search?q=``. ``total`` = cantidad de hits."""

    query: str
    total: int
    results: list[MemorySearchHit]
