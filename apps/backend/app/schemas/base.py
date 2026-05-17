"""Base común para schemas Pydantic de Ynara."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class YnaraBaseModel(BaseModel):
    """Base con configuración estándar para todos los schemas.

    - ``strict=True``: no coerción silenciosa de tipos.
    - ``from_attributes=True``: permite construir desde objetos ORM.
    - ``populate_by_name=True``: aliases y nombres conviven.
    """

    model_config = ConfigDict(
        strict=True,
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )
