"""Capas de memoria de Ynara.

- ``semantic`` — hechos persistentes, Mem0 + pgvector.
- ``episodic`` — resúmenes de sesiones, pgvector.
- ``procedural`` — preferencias y patrones, JSONB.

Las tres tablas son **sagradas** (regla #3 de AGENTS.md): cualquier
toque al esquema requiere tests + 2 aprobaciones humanas.
"""
