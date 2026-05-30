"""Capas de memoria de Ynara — storage propio cifrado (engine in-house, ADR-010).

- ``semantic`` — hechos persistentes, cifrados AES-256-GCM + embedding 1024-dim
  en pgvector. Storage hand-rolled (NADA de Mem0, ADR-010 supersede ADR-003).
- ``episodic`` — resúmenes de sesiones, cifrados + embedding en pgvector.
- ``procedural`` — preferencias y patrones, JSONB plain (sin cifrado, sin
  embedding), lookup por ``(user_id, key)``.

Cada capa expone un ``*Store`` que se construye **por request** ligando el
``user_id`` en el ``__init__`` (la key de cifrado se deriva de ``user_id``, así
que el aislamiento entre usuarios es estructural).

Las tres tablas son **sagradas** (regla #3 de AGENTS.md): cualquier toque al
esquema requiere tests + 1 aprobación humana explícita (review formal en el PR,
además del operador autor).
"""

from __future__ import annotations

from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore

__all__ = [
    "EpisodicMemoryStore",
    "ProceduralMemoryStore",
    "SemanticMemoryStore",
]
