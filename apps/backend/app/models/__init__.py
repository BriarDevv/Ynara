"""Modelos SQLAlchemy de Ynara.

Cualquier modelo nuevo se documenta en ``apps/backend/docs/MODELS.md``.
Tablas sagradas (memoria) tienen reglas especiales: ver
``apps/backend/AGENTS.md``.
"""

from app.models.base import Base

__all__ = ["Base"]
