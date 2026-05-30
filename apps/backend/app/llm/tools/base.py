"""Contrato base de las tools que Qwen puede llamar (M6).

``Tool`` es el Protocol que toda tool implementa: expone su identidad
(``name`` en formato ``namespace.action`` snake_case, ``namespace``,
``description``), su JSON Schema de parametros (formato OpenAI tool-calling)
y un ``execute`` async.

Regla del repo (``docs/TOOLS.md``): los errores de ejecucion se devuelven
como dict estructurado ``{"error": {"code": ..., "message": ...}}``, NUNCA
como excepcion que escape al modelo. ``tool_error`` arma ese dict; el
registry (``registry.py``) envuelve cualquier excepcion que se escape de un
``execute`` para que el modelo jamas vea un traceback.

``to_spec`` arma el ``ToolSpec`` (de ``schemas.py``) en el formato OpenAI
que el cliente vLLM espera: ``{"type": "function", "function": {...}}`` vive
en la capa de serializacion del cliente; aca ``ToolSpec`` guarda
``name`` / ``description`` / ``parameters`` planos y el cliente los envuelve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BeforeValidator, Field

from app.llm.schemas import ToolSpec


def _reject_numeric_datetime(value: object) -> object:
    """Rechaza timestamps numericos en los campos datetime de las tool calls.

    Las tool calls mandan fechas como string ISO 8601 (contrato
    ``docs/TOOLS.md``). Con ``strict=False`` Pydantic coerceria un epoch
    int/float a una fecha plausible-pero-incorrecta; si el modelo alucina un
    numero preferimos ``invalid_arguments`` antes que agendar en la fecha
    equivocada.
    """
    if isinstance(value, (int, float)):
        raise ValueError("se espera un string ISO 8601, no un timestamp numerico")
    return value


# ``IsoDatetime``: datetime de tool call — acepta string ISO 8601, rechaza epoch numerico.
IsoDatetime = Annotated[datetime, BeforeValidator(_reject_numeric_datetime), Field(strict=False)]


@runtime_checkable
class Tool(Protocol):
    """Una tool invocable por el agente Qwen.

    El ``name`` sigue ``namespace.action`` (ambos snake_case). El
    ``namespace`` se declara por separado: es la clave de habilitacion por
    modo en ``ynara.config.json[modes][*].tools_enabled`` y la que el
    registry usa para filtrar que tools ve cada modo.
    """

    @property
    def name(self) -> str:
        """Identificador unico ``namespace.action``."""
        ...

    @property
    def namespace(self) -> str:
        """Namespace de habilitacion por modo (``calendar``, ``reminder``)."""
        ...

    @property
    def description(self) -> str:
        """Descripcion para el modelo (que hace la tool, en una linea)."""
        ...

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema OpenAI de los argumentos (``type: object``)."""
        ...

    async def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        """Ejecuta la tool y devuelve un dict de resultado.

        Nunca debe propagar una excepcion al modelo: los errores se
        devuelven con ``tool_error``. Aun asi, el registry envuelve por las
        dudas cualquier excepcion que se escape.
        """
        ...


def to_spec(tool: Tool) -> ToolSpec:
    """Arma el ``ToolSpec`` neutro de una tool.

    El cliente vLLM se encarga de envolverlo en el wire OpenAI
    (``{"type": "function", "function": {...}}``); aca solo aplanamos la
    identidad + el JSON Schema.
    """
    return ToolSpec(
        name=tool.name,
        description=tool.description,
        parameters=dict(tool.parameters),
    )


def tool_error(code: str, message: str) -> dict[str, object]:
    """Construye el dict de error estructurado que ve el modelo.

    Formato fijo (``docs/TOOLS.md``): ``{"error": {"code", "message"}}``. El
    ``message`` es una etiqueta tecnica corta, sin datos sensibles del
    usuario (regla #4).
    """
    return {"error": {"code": code, "message": message}}
