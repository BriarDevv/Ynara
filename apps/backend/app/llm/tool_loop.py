"""Tool loop del router LLM (M8 Ola 1).

Ejecuta iteraciones de llamada al LLM + ejecucion de tools hasta que el
modelo termina (finish_reason in {'stop','length','degraded'}) o se agotan
las iteraciones del guard (MAX_TOOL_ITERATIONS).

Notas y limitaciones conocidas:
- El ``ChatMessage`` de assistant SI preserva ``tool_calls`` (M9): es el
  prerequisito para que el parser hermes de Qwen real correlacione la respuesta
  ``role='tool'`` con su llamada en multi-turn. Con FakeLlmClient es inocuo; la
  correlacion contra Qwen real todavia no esta validada E2E (infra-swap).
- No hay historial multi-turno persistido: cada llamada a ``run_tool_loop``
  parte de los mensajes que recibe (system + user). El historial vivo de la
  sesion sigue siendo trabajo posterior (no lo entrega M9).
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
) -> tuple[str, list[dict[str, object]], str]:
    """Loop principal de inferencia + ejecucion de tools.

    Por cada iteracion:
    1. Llama a ``llm_client.complete(model=served_name, messages=messages,
       tools=specs or None)``.
    2. Termina si no hay tool_calls O si finish_reason es terminal
       (``stop`` / ``length`` / ``degraded``).
    3. Si hay tool_calls: agrega un ChatMessage(role='assistant') al historial
       con ``tool_calls`` preservado, ejecuta cada tool via
       ``_execute_anywhere``, acumula en ``actions`` y agrega un
       ChatMessage(role='tool') por cada resultado.
    4. Al agotar ``max_iterations`` sin converger, usa el ultimo ``result.text``
       como texto final; si esta vacio, usa ``fallback_text``. finish_reason
       reportado sera ``'max_iterations'`` (parada forzada por el guard; un
       sentinel honesto para telemetria, no se confunde con un ``'stop'`` real).

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
        Tupla ``(text, actions, finish_reason)`` donde:
        - ``text``: Respuesta final del modelo (nunca vacia: usa fallback_text).
        - ``actions``: Lista de dicts
          ``{'id': str, 'name': str, 'arguments': dict, 'result': dict}``
          de las tools ejecutadas, en orden de ejecucion.
        - ``finish_reason``: El ``finish_reason`` del ultimo ``CompletionResult``
          procesado, o ``'max_iterations'`` si se agoto el guard sin converger.
    """
    actions: list[dict[str, object]] = []
    tool_specs: list[ToolSpec] | None = specs if specs else None

    last_text: str = ""
    last_finish_reason: str = "stop"

    for _ in range(max_iterations):
        result = await llm_client.complete(
            model=served_name,
            messages=messages,
            tools=tool_specs,
        )
        last_text = result.text
        last_finish_reason = result.finish_reason

        # Sin tool_calls o finish_reason terminal -> terminar
        if not result.tool_calls or result.finish_reason in _TERMINAL_REASONS:
            break

        # Agregar turno del assistant al historial CON tool_calls preservado
        # (necesario para multi-turno correcto con Qwen/hermes parser).
        messages.append(
            ChatMessage(
                role="assistant",
                content=result.text or None,
                tool_calls=list(result.tool_calls),
            )
        )

        # Ejecutar cada tool call y acumular en actions + historial.
        tool_call: ToolCall
        for tool_call in result.tool_calls:
            tool_result = await _execute_anywhere(
                tool_call.name, tool_call.arguments, registries
            )
            actions.append(
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result": tool_result,
                }
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=json.dumps(tool_result, ensure_ascii=False),
                )
            )
    else:
        # Guard agotado sin converger: last_text tiene el texto de la ultima
        # iteracion; finish_reason se marca 'max_iterations' (sentinel honesto
        # para no confundir una parada forzada con un 'stop' real del modelo).
        last_finish_reason = "max_iterations"

    final_text = last_text if last_text else fallback_text
    return final_text, actions, last_finish_reason
