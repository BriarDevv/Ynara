"""Tool loop del router LLM (M8 Ola 1).

Ejecuta iteraciones de llamada al LLM + ejecucion de tools hasta que el
modelo termina (finish_reason in {'stop','length','degraded'}) o se agotan
las iteraciones del guard (MAX_TOOL_ITERATIONS).

Limitaciones conocidas de M8:
- El ``ChatMessage`` de assistant que se agrega al historial NO preserva
  ``tool_calls`` (el schema de ChatMessage no tiene ese campo). Con
  FakeLlmClient esto es inocuo; con Qwen real via el parser hermes la
  correlacion de tool_calls podria requerir ese campo para multi-turn correcto.
  Riesgo de infra-swap a verificar en M9.
- No hay historial multi-turno persistido: cada llamada a ``run_tool_loop``
  parte de los mensajes que recibe (system + user). El historial vivo de la
  sesion es M9 (ChatSession persistida).
"""

from __future__ import annotations

import json

from app.llm.schemas import ChatMessage, ToolCall, ToolSpec
from app.llm.tools.base import tool_error
from app.llm.tools.registry import ToolRegistry

MAX_TOOL_ITERATIONS: int = 5

# finish_reason que indica que el loop debe terminar (con o sin tool_calls).
_TERMINAL_REASONS = frozenset({"stop", "length", "degraded"})


async def _execute_anywhere(
    name: str,
    args: dict[str, object],
    registries: tuple[ToolRegistry, ToolRegistry | None],
) -> dict[str, object]:
    """Busca ``name`` en cada registry no-None y ejecuta la primera que lo tenga.

    Si ninguna lo tiene, devuelve ``tool_error('unknown_tool', ...)``.
    La ejecucion ya esta blindada en ``ToolRegistry.execute``: nunca propaga
    excepcion, devuelve ``tool_error('execution_error', ...)`` si falla.

    Args:
        name: Nombre de la tool (``namespace.action``).
        args: Argumentos ya parseados de la tool call.
        registries: Tupla (default_registry, memory_registry|None).

    Returns:
        Dict de resultado de la tool (o de error estructurado).
    """
    for reg in registries:
        if reg is not None and reg.has(name):
            return await reg.execute(name, args)
    return tool_error("unknown_tool", f"tool desconocida: {name}")


async def run_tool_loop(
    *,
    llm_client: object,
    served_name: str,
    messages: list[ChatMessage],
    specs: list[ToolSpec],
    registries: tuple[ToolRegistry, ToolRegistry | None],
    max_iterations: int = MAX_TOOL_ITERATIONS,
    fallback_text: str,
) -> tuple[str, list[dict[str, object]]]:
    """Loop principal de inferencia + ejecucion de tools.

    Por cada iteracion:
    1. Llama a ``llm_client.complete(model=served_name, messages=messages,
       tools=specs or None)``.
    2. Termina si no hay tool_calls O si finish_reason es terminal
       (``stop`` / ``length`` / ``degraded``).
    3. Si hay tool_calls: agrega un ChatMessage(role='assistant') al historial,
       ejecuta cada tool via ``_execute_anywhere``, acumula en ``actions`` y
       agrega un ChatMessage(role='tool') por cada resultado.
    4. Al agotar ``max_iterations`` sin converger, usa el ultimo ``result.text``
       como texto final; si esta vacio, usa ``fallback_text``.

    NOTA: el ChatMessage del assistant NO preserva ``tool_calls`` (el schema no
    tiene ese campo). Con FakeLlmClient esto es inocuo; con Qwen real via el
    parser hermes podria requerir correlacion -> riesgo de infra-swap a
    verificar en M9.

    Args:
        llm_client: Implementacion de ``LLMClient`` (real o fake).
        served_name: ``served_name`` del modelo (ej. ``'qwen'`` o ``'gemma4'``).
            Siempre el ``served_name``, NUNCA la key interna (decision #5).
        messages: Historial inicial (system + user actual). Se muta con los
            turnos del tool loop; el caller puede pasar una copia si necesita
            preservar el original.
        specs: ``ToolSpec`` a pasar al modelo; ``None`` si la lista esta vacia
            (Gemma conversacional no ve tools).
        registries: Tupla ``(default_registry, memory_registry|None)`` de
            ``MemoryContext.registries``.
        max_iterations: Guard maximo de iteraciones (default ``MAX_TOOL_ITERATIONS``).
        fallback_text: Texto de fallback si el texto final esta vacio.

    Returns:
        Tupla ``(text, actions)`` donde:
        - ``text``: Respuesta final del modelo (nunca vacia: usa fallback_text).
        - ``actions``: Lista de dicts ``{'name': str, 'result': dict}`` de las
          tools ejecutadas, en orden de ejecucion.
    """
    actions: list[dict[str, object]] = []
    tool_specs: list[ToolSpec] | None = specs if specs else None

    last_text: str = ""

    for _ in range(max_iterations):
        result = await llm_client.complete(
            model=served_name,
            messages=messages,
            tools=tool_specs,
        )
        last_text = result.text

        # Sin tool_calls o finish_reason terminal -> terminar
        if not result.tool_calls or result.finish_reason in _TERMINAL_REASONS:
            break

        # Agregar turno del assistant al historial (SIN tool_calls: ver NOTA).
        messages.append(
            ChatMessage(role="assistant", content=result.text or None)
        )

        # Ejecutar cada tool call y acumular en actions + historial.
        tool_call: ToolCall
        for tool_call in result.tool_calls:
            tool_result = await _execute_anywhere(
                tool_call.name, tool_call.arguments, registries
            )
            actions.append({"name": tool_call.name, "result": tool_result})
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=json.dumps(tool_result, ensure_ascii=False),
                )
            )
    else:
        # Guard agotado: last_text ya tiene el texto de la ultima iteracion.
        pass

    final_text = last_text if last_text else fallback_text
    return final_text, actions
