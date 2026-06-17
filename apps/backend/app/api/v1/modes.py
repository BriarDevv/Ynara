"""Catálogo de modos: ``GET /v1/modes``.

Expone la lista de modos declarados en ``ynara.config.json[modes]`` (id +
metadata semántica: ``model``, ``memory_layers``, ``tools_enabled``, ``tone``).
Es la fuente **server-driven** que consume el Mode Switcher del front (build-plan
track backend #1): hasta ahora el front leía el mismo bloque en build time
(``apps/web/src/lib/modes.ts``); este endpoint deja cambiar los modos sin rebuild.

Decisiones:

- **Sin auth** (mismo tier que ``/health``): es metadata pública de producto, no
  datos de usuario. Los mismos campos ya viajan en el bundle del front (que
  importa ``ynara.config.json`` en build), así que el endpoint no expone nada
  nuevo. Sin DB ni Redis: lee la config de runtime ya cacheada.
- **Mirror de la config** (Pydantic gana, Zod sigue): ``ModeOut`` espeja el shape
  de ``ConfigModeSchema`` del front + el ``id``. El front mapea cada ``id`` a su
  label/gradiente local (``apps/web/src/components/ui/modes.ts``).
- **Orden de declaración**: el dict de modos preserva el orden del JSON, que es el
  orden en que el switcher los muestra.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.enums import Mode
from app.llm.config import ModeConfig, load_llm_config

router = APIRouter()


class ModeOut(BaseModel):
    """Un modo del catálogo. Mirror de ``ynara.config.json[modes][<id>]``.

    ``id`` es la clave del modo, validada contra el enum ``Mode`` (si la config
    declarara un modo desconocido, ``Mode(id)`` levantaría — fail-fast, pero la
    coherencia config↔enum ya se valida en otro lado). El resto espeja el JSON 1:1.
    """

    model_config = ConfigDict(frozen=True)

    id: Mode
    model: str
    memory_layers: list[str]
    tools_enabled: list[str]
    tone: str


class ModesResponse(BaseModel):
    """Catálogo de modos en orden de declaración de la config."""

    modes: list[ModeOut]


def build_modes_response(modes: dict[str, ModeConfig]) -> ModesResponse:
    """Convierte el dict ``{id: ModeConfig}`` en la respuesta, preservando el orden.

    Pura y testeable sin tocar la config real ni el loader del LLM.
    """
    return ModesResponse(
        modes=[
            ModeOut(
                id=Mode(mode_id),
                model=cfg.model,
                memory_layers=list(cfg.memory_layers),
                tools_enabled=list(cfg.tools_enabled),
                tone=cfg.tone,
            )
            for mode_id, cfg in modes.items()
        ]
    )


def get_available_modes() -> dict[str, ModeConfig]:
    """Dependencia: los modos de la config de runtime (cacheada).

    Inyectable: los tests la overridean para no depender del loader del LLM (que
    valida ``LLM_SERVING`` y demás infra ajena al catálogo de modos).
    """
    return load_llm_config().modes


@router.get("/modes", response_model=ModesResponse, status_code=200)
async def list_modes(
    modes: Annotated[dict[str, ModeConfig], Depends(get_available_modes)],
) -> ModesResponse:
    """Lista los modos disponibles (id + metadata semántica de la config).

    Solo lectura, sin auth, sin DB: espeja ``ynara.config.json[modes]``.
    """
    return build_modes_response(modes)
