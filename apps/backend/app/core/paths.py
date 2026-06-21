"""Resolución robusta de la ruta de ``ynara.config.json`` (contrato de producto).

``ynara.config.json`` (models / modes / llm.serving + el bloque ``[memory]``) vive
en la raíz del repo en desarrollo, pero la imagen de producción lo copia a otra
ruta (``/app/ynara.config.json``). Resolver la ruta con un ``parents[N]`` fijo
asumía el layout del repo y **rompía en el contenedor con ``IndexError``** (el
código vive en ``/app/app/llm/config.py``, sin 4 niveles de ancestros) — lo que
impedía que la imagen booteara la app.

``resolve_config_path()`` resuelve en orden, de forma independiente del layout:

1. ``YNARA_CONFIG_PATH`` (env): override explícito (la imagen lo setea).
2. **Walk-up** desde este archivo buscando ``ynara.config.json`` (dev: raíz del
   repo; contenedor: ``/app`` si el JSON se copió ahí).
3. ``CWD/ynara.config.json`` como último recurso.

NO se cachea con ``lru_cache``: el cálculo es barato y los loaders que la usan
(``app/llm/config.py`` / ``app/memory/config.py``) ya cachean su resultado, así que
se invoca pocas veces; sin cache queda testeable con ``monkeypatch.setenv`` sin
tener que limpiar estado entre casos.
"""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_FILENAME = "ynara.config.json"
_ENV_VAR = "YNARA_CONFIG_PATH"


def resolve_config_path() -> Path:
    """Devuelve la ruta a ``ynara.config.json`` resolviendo env → walk-up → CWD.

    No verifica que el archivo exista (eso lo maneja el lector del config con su
    propio error tipado); solo decide *qué* ruta usar de forma robusta al layout.
    """
    env_override = os.environ.get(_ENV_VAR)
    if env_override:
        return Path(env_override)

    for parent in Path(__file__).resolve().parents:
        candidate = parent / _CONFIG_FILENAME
        if candidate.exists():
            return candidate

    return Path.cwd() / _CONFIG_FILENAME
