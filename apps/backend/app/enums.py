"""Enums compartidos cross-domain de Ynara.

Convención: los enums que aparecen en columnas de DB y en payloads de API
(o en routing LLM) viven acá, no duplicados por dominio. Pydantic schemas
y modelos SQLAlchemy importan desde este archivo.

Naming en Postgres: el nombre del tipo PostgreSQL queda definido en el
``Enum`` de SQLAlchemy del modelo que lo usa primero (ver ``app/models/``).
"""

from __future__ import annotations

from enum import StrEnum


class Mode(StrEnum):
    """Modos de Ynara. Ver ``ynara.config.json[modes]`` y ADR-002."""

    PRODUCTIVIDAD = "productividad"
    ESTUDIO = "estudio"
    BIENESTAR = "bienestar"
    VIDA = "vida"
    MEMORIA = "memoria"


class MemoryLayer(StrEnum):
    """Capa de memoria. Ver ``docs/product/MEMORY.md`` y ADR-003."""

    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class LlmModel(StrEnum):
    """Modelo LLM que actuó como origen de una operación. Ver ADR-002."""

    GEMMA = "gemma"
    QWEN = "qwen"


class AuditOperation(StrEnum):
    """Operaciones registradas en audit_log."""

    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
