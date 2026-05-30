"""Registro de tools del agente Qwen (M6).

``ToolRegistry`` mapea ``name -> Tool`` y conoce el ``namespace`` de cada
una. El router (M8) le pasa los namespaces habilitados para el modo activo
(``tools_enabled`` de ``ynara.config.json``) y obtiene los ``ToolSpec`` a
mandar al modelo; cuando el modelo pide una tool, el registry la ejecuta y
**envuelve cualquier excepcion** en el dict de error estructurado, asi el
modelo nunca ve un traceback.

El registry no filtra por modelo: que solo los modos Qwen reciban tools lo
decide el router via ``tools_enabled`` (los modos Gemma tienen la lista
vacia: son solo conversacionales, ADR-002; el routing real es M8).
"""

from __future__ import annotations

from app.llm.schemas import ToolSpec
from app.llm.tools.base import Tool, to_spec, tool_error
from app.llm.tools.calendar import CreateEventTool, ListEventsTool
from app.llm.tools.reminder import ListRemindersTool, SetReminderTool


class ToolRegistry:
    """Coleccion de tools indexadas por ``name``."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Agrega una tool. Falla fuerte si el ``name`` ya existe."""
        if tool.name in self._tools:
            raise ValueError(f"tool duplicada: {tool.name}")
        self._tools[tool.name] = tool

    def specs_for(self, enabled_namespaces: list[str]) -> list[ToolSpec]:
        """``ToolSpec`` de las tools cuyo namespace este habilitado.

        Orden estable de registro (dict preserva insercion) para que el
        prompt sea determinista. Namespaces no habilitados se ignoran.
        """
        enabled = set(enabled_namespaces)
        return [to_spec(tool) for tool in self._tools.values() if tool.namespace in enabled]

    async def execute(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Resuelve por ``name``, ejecuta y blinda contra excepciones.

        - tool desconocida -> ``tool_error("unknown_tool", ...)``.
        - cualquier excepcion del ``execute`` -> ``tool_error("execution_error",
          ...)``. El modelo nunca recibe un traceback ni un ``raise``.
        """
        tool = self._tools.get(name)
        if tool is None:
            return tool_error("unknown_tool", f"tool desconocida: {name}")
        try:
            return await tool.execute(arguments)
        except Exception:
            # Blindaje: el modelo nunca debe ver un traceback (docs/TOOLS.md).
            return tool_error("execution_error", f"fallo ejecutando {name}")


def default_registry() -> ToolRegistry:
    """Registry por defecto: calendar + reminder (NO memory).

    Memory es M7 (tabla sagrada, regla #3) y se registra aparte cuando
    exista. Aca solo van las 4 tools stub de M6.
    """
    return ToolRegistry(
        [
            CreateEventTool(),
            ListEventsTool(),
            SetReminderTool(),
            ListRemindersTool(),
        ]
    )
