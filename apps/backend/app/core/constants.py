"""Constantes transversales del backend, sin dependencias del proyecto.

Este módulo es la **fuente única de verdad** de valores que comparten capas que
no deberían acoplarse entre sí (p. ej. la capa de clientes LLM y la capa de
modelos SQLAlchemy). Vive en ``app/core`` y **no importa nada del proyecto**
(ni SQLAlchemy ni los modelos sagrados), para que cualquier capa pueda
importarlo sin arrastrar dependencias pesadas ni crear ciclos de imports.
"""

from __future__ import annotations

# Dimensión del embedding denso de bge-m3 (ADR-008/ADR-009). Fuente única de
# verdad: la importan tanto la capa LLM (``app/llm/clients/embedding.py``) como
# la capa de modelos (``app/models/memory.py``, ``Vector(EMBEDDING_DIM)``). El
# valor 1024 es estable hasta un ADR nuevo; al estar centralizado, cambia en un
# solo lugar (con su gate sagrado, regla #3, por el impacto en la tabla).
EMBEDDING_DIM = 1024
