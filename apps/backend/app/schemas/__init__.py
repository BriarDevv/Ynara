"""Schemas Pydantic v2 de request/response.

Convención: un archivo por dominio (``auth.py``, ``chat.py``,
``memory.py``). Cuando los schemas se usan también desde el frontend,
considerar exponerlos también desde ``packages/shared-schemas`` en TS
(Zod) — pero la fuente de verdad sigue siendo Pydantic acá.
"""

from app.schemas.base import YnaraBaseModel

__all__ = ["YnaraBaseModel"]
