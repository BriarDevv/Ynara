"""Schemas Pydantic del intake de onboarding (``POST /v1/onboarding``).

Contrato congelado en ADR-026. El **mirror Pydantic** (fuente de verdad) vive acá;
el Zod en ``packages/shared-schemas`` lo sigue ("Pydantic gana, Zod sigue"). El wire
es snake_case.

Routing de cada señal (ADR-026 §2): lo **OPERATIVO** aterriza en ``users`` —
``display_name`` + ``interested_modes``/``a11y`` (``users.preferences`` JSONB). Lo
**memory-bound** (``mood``/``mood_free_text``/``about``, SAGRADO regla #3) lo consume
G4 (``seed_onboarding_memory``): siembra hechos semánticos (ánimo + sobre-vos) y la
dedicación como preferencia procedural, en la misma llamada al endpoint.

``UserPreferences`` es la forma TIPADA de ``users.preferences`` (lo que el endpoint
escribe); ``UserOut.preferences`` viaja como ``dict`` RAW (las filas viejas tienen ``{}``
y no validarían contra ``UserPreferences`` — el FE le da forma con Zod).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from app.enums import Mode
from app.schemas.base import YnaraBaseModel

# Los bodies de request reciben tipos del wire como strings JSON (``interested_modes``
# str->Mode enum, ``a11y.text_size`` str->Literal). Bajo el ``strict=True`` heredado de
# ``YnaraBaseModel`` eso se rechaza, así que los schemas de request override-an
# ``strict=False`` a nivel modelo (MISMO patrón que ``ReminderCreate`` / ``TaskCreate``)
# manteniendo constraints + ``extra='forbid'``.
_WIRE_REQUEST_CONFIG = ConfigDict(
    strict=False,
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)

# "sobre vos" — cotas razonables para los campos free-text (anti-inflado del body). El
# default ``""`` (no ``None``) refleja el draft del FE: el step puede dejar campos vacíos.
_AboutText = Annotated[str, Field(default="", max_length=200)]


class A11yPrefs(YnaraBaseModel):
    """Prefs de accesibilidad (OPERATIVO). Espeja ``useA11yStore`` del FE."""

    model_config = _WIRE_REQUEST_CONFIG

    text_size: Literal["sm", "md", "lg"]
    high_contrast: bool
    motion: Literal["auto", "reduce", "normal"]


class UserPreferences(YnaraBaseModel):
    """Forma TIPADA de ``users.preferences`` (JSONB): lo OPERATIVO del onboarding.

    Es lo que el endpoint ESCRIBE en la columna. ``UserOut.preferences`` viaja como
    ``dict`` RAW (no este tipo): las filas pre-onboarding tienen ``{}`` y no validarían acá.
    """

    interested_modes: list[Mode]
    a11y: A11yPrefs


class AboutYou(YnaraBaseModel):
    """ "Sobre vos" — la señal memory-bound más rica (a qué se dedica, qué estudia, etc.).

    G4 la siembra en memoria: ``study_what``/``work_what``/``purpose``/``interests`` como
    hechos semánticos y ``dedication`` como preferencia procedural. ``null`` si el usuario
    saltó el step entero.
    """

    model_config = _WIRE_REQUEST_CONFIG

    dedication: Literal["estudio", "trabajo", "ambos", "otro"] | None = None
    study_what: _AboutText
    work_what: _AboutText
    purpose: _AboutText
    interests: _AboutText


class OnboardingIntake(YnaraBaseModel):
    """Body de ``POST /v1/onboarding`` — el intake completo del onboarding (ADR-026).

    Mezcla OPERATIVO (``display_name`` + ``interested_modes`` + ``a11y``) con memory-bound
    (``mood`` + ``mood_free_text`` + ``about``). El endpoint persiste lo operativo en
    ``users`` y siembra lo memory-bound en memoria (G4, ``seed_onboarding_memory``).
    """

    model_config = _WIRE_REQUEST_CONFIG

    display_name: str = Field(max_length=40)
    # ``>= 1``: el onboarding exige al menos un modo de interés (gate del step "modos").
    interested_modes: list[Mode] = Field(min_length=1)
    a11y: A11yPrefs
    # memory-bound (G4): se acepta/valida, NO se persiste todavía.
    mood: list[str] = Field(default_factory=list, max_length=2)
    mood_free_text: str | None = Field(default=None, max_length=160)
    about: AboutYou | None = None
