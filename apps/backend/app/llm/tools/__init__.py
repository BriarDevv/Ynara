"""Tools que Qwen 3.5-9B (modo agente) puede llamar.

Convención: un módulo por namespace (``calendar.py``, ``reminder.py``,
``memory.py``, ``mode.py``). Cada tool implementa el Protocol ``Tool``
(``base.py``): expone ``name`` (``namespace.action`` snake_case),
``namespace``, ``description``, ``parameters`` (JSON Schema OpenAI) y un
``execute`` async. El ``ToolRegistry`` (``registry.py``) las indexa por
``name``, arma los ``ToolSpec`` por modo (``specs_for``) y blinda la
ejecución contra excepciones: los errores siempre vuelven como dict
estructurado ``{"error": {"code", "message"}}`` (``tool_error``), nunca como
traceback hacia el modelo.

``memory.py`` es M7 (tabla sagrada, regla #3): NO está acá todavía y
``default_registry`` no la incluye.

Documentadas en ``apps/backend/docs/TOOLS.md`` — actualizar en el
mismo PR cuando se agreguen.
"""

from __future__ import annotations

from app.llm.tools.base import Tool, to_spec, tool_error
from app.llm.tools.registry import ToolRegistry, default_registry

__all__ = [
    "Tool",
    "ToolRegistry",
    "default_registry",
    "to_spec",
    "tool_error",
]
