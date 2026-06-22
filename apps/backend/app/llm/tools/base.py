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
que el cliente LLM (OpenAI-compatible) espera: ``{"type": "function",
"function": {...}}`` vive en la capa de serializacion del cliente; aca
``ToolSpec`` guarda ``name`` / ``description`` / ``parameters`` planos y el
cliente los envuelve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, BeforeValidator, ValidationError

from app.llm.schemas import ToolSpec


def _coerce_iso_datetime(value: object) -> object:
    """Acepta ``datetime`` nativo o string ISO 8601; rechaza epoch numerico.

    Las tool calls mandan fechas como string ISO 8601 (contrato
    ``docs/TOOLS.md``). Con ``strict=False`` Pydantic coerceria tanto un epoch
    crudo (``int``/``float``) como una string puramente numerica
    (``"1716000000"``) a una fecha plausible-pero-incorrecta. Parseamos la
    string con ``datetime.fromisoformat`` (ISO estricto): asi un epoch
    alucinado -> ``invalid_arguments`` en vez de agendar en la fecha
    equivocada. Devolver un ``datetime`` deja que el modelo strict lo acepte.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("se espera un string ISO 8601 valido") from exc
    raise ValueError("se espera un string ISO 8601, no un timestamp numerico")


# ``IsoDatetime``: datetime de tool call — solo string ISO 8601 (o datetime nativo).
IsoDatetime = Annotated[datetime, BeforeValidator(_coerce_iso_datetime)]

# Tope de filas que una tool de listado del agente (``calendar.list_events`` /
# ``task.list_tasks``) devuelve al tool-loop. Defensa en profundidad (lección de la review
# de las tools síncronas): el resultado de la tool se inyecta en el historial de mensajes
# del LLM (``json.dumps`` en ``tool_loop``), así que un usuario con miles de eventos/tareas
# inundaría el context window con un solo turno (vector de costo + de inyección de strings
# controladas por el usuario). El cap acota ese fan-out; el CRUD HTTP NO lo usa (su contrato
# es la lista completa). 50 es un techo holgado para "qué tengo agendado/pendiente".
AGENT_LIST_RESULT_LIMIT: int = 50


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

    El cliente LLM (OpenAI-compatible) se encarga de envolverlo en el wire
    OpenAI (``{"type": "function", "function": {...}}``); aca solo aplanamos la
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


def tool_schema(model: type[BaseModel]) -> dict[str, object]:
    """JSON Schema OpenAI de los argumentos de una tool.

    Quita la ``description`` top-level: el docstring del modelo Pydantic es
    ruido interno para el modelo (la descripcion util de la tool va en
    ``Tool.description``). Las descripciones por-campo (``Field(description=)``)
    se conservan.
    """
    schema = model.model_json_schema()
    schema.pop("description", None)
    return schema


def not_wired_result(
    action: str, arguments: dict[str, object], *, detail: str
) -> dict[str, object]:
    """Resultado stub uniforme para una tool sin backend real cableado."""
    return {"status": "not_wired", "detail": detail, "action": action, "echo": arguments}


def first_validation_error(exc: ValidationError) -> str:
    """Etiqueta tecnica corta del primer error de validacion.

    No vuelca el valor recibido (regla #4: nada de datos del usuario en el
    texto): solo la ubicacion del campo y el tipo de error.
    """
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"]) or "(root)"
    return f"argumento invalido en '{loc}': {err['type']}"
