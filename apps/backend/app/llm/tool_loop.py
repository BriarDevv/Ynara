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
from dataclasses import dataclass

from app.llm.schemas import ChatMessage, ToolCall, ToolSpec
from app.llm.tools.base import tool_error
from app.llm.tools.registry import ToolRegistry

MAX_TOOL_ITERATIONS: int = 5

# Tope defensivo de tool_calls a ejecutar por turno. Si el modelo emite mas, se
# ejecutan solo las primeras ``MAX_CALLS_PER_TURN`` (las extra se descartan).
# Acota el fan-out de un turno patologico (modelo en loop emitiendo decenas de
# calls) sin cambiar el camino feliz, donde un turno trae pocas calls.
MAX_CALLS_PER_TURN: int = 8

# Tope de bytes del JSON de UN resultado de tool antes de inyectarlo en el historial de
# mensajes del LLM. Defensa en profundidad sobre el cap por-tool (las list tools ya acotan
# filas con ``AGENT_LIST_RESULT_LIMIT``): cualquier resultado anormalmente grande (una tool
# futura sin cap, o un dict patologico) NO inunda el context window. Si se excede, el
# resultado real se reemplaza por un ``tool_error`` estructurado (el modelo ve "el resultado
# era demasiado grande", no el payload). El cap es generoso (32KB) para no truncar listas
# legitimas dentro del ``AGENT_LIST_RESULT_LIMIT``.
TOOL_RESULT_MAX_BYTES: int = 32_768

# finish_reason que indica que el loop debe terminar (con o sin tool_calls).
_TERMINAL_REASONS = frozenset({"stop", "length", "degraded"})


@dataclass(frozen=True)
class ToolLoopResult:
    """Resultado inmutable del tool loop (reemplaza la 4-tupla mixta previa).

    Contenedor con campos nombrados (coding-style del repo) en vez de una tupla
    posicional:

    - ``text``: respuesta final del modelo (nunca vacia: usa ``fallback_text``).
    - ``actions``: tools ejecutadas, en orden, como dicts
      ``{'id', 'name', 'arguments', 'result'}``.
    - ``finish_reason``: ``finish_reason`` del ultimo ``CompletionResult`` procesado,
      o ``'max_iterations'`` si se agoto el guard sin converger.
    - ``reasoning``: razonamiento del modelo (canal ``reasoning`` SEPARADO de cada
      ``CompletionResult``) acumulado y concatenado a lo largo de TODAS las iteraciones
      del loop, igual que ``actions``. ``None`` si ninguna iteracion expuso razonamiento
      (thinking off, o modelo sin canal de razonamiento). Aditivo: los consumidores que
      lo ignoran no cambian.
    """

    text: str
    actions: list[dict[str, object]]
    finish_reason: str
    reasoning: str | None = None


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
    thinking: bool | None = None,
    fallback_text: str,
) -> ToolLoopResult:
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
       como texto final; si esta vacio, fuerza UNA completion final SIN tools para
       que el modelo responda en lenguaje natural (en vez de seguir tool-calleando) y
       el usuario vea una respuesta real, no el ``fallback_text`` generico. Si esa
       completion forzada tambien vuelve vacia, recien ahi se usa ``fallback_text``.
       finish_reason reportado sera ``'max_iterations'`` (parada forzada por el guard;
       un sentinel honesto para telemetria, no se confunde con un ``'stop'`` real).

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
        thinking: Modo de razonamiento del modelo (ADR-012 D4). ``None`` deja el
            default del server; ``True``/``False`` lo fuerza ON/OFF. Passthrough
            puro hacia ``llm_client.complete``; lo decide el router por rol.
        fallback_text: Texto de fallback si el texto final esta vacio.

    Returns:
        Un ``ToolLoopResult`` (inmutable) con ``text``, ``actions``, ``finish_reason``
        y ``reasoning`` (ver el docstring del dataclass). El ``reasoning`` acumula el
        canal de razonamiento separado de cada iteracion del loop (concatenado), igual
        que ``actions`` acumula las tools ejecutadas; ``None`` si ninguna iteracion
        expuso razonamiento.
    """
    actions: list[dict[str, object]] = []
    tool_specs: list[ToolSpec] | None = specs if specs else None

    last_text: str = ""
    last_finish_reason: str = "stop"
    # Razonamiento acumulado de TODAS las iteraciones (patron ``reasoning_parts`` del
    # playground): cada ``CompletionResult`` trae el canal de razonamiento SEPARADO del
    # ``content``; se concatena al final. Hoy el router lo descartaba; ahora se devuelve
    # para que el endpoint pueda re-trocearlo como evento SSE ``reasoning``.
    reasoning_parts: list[str] = []

    for _ in range(max_iterations):
        result = await llm_client.complete(
            model=served_name,
            messages=messages,
            tools=tool_specs,
            thinking=thinking,
        )
        last_text = result.text
        last_finish_reason = result.finish_reason
        if result.reasoning:
            reasoning_parts.append(result.reasoning)

        # Sin tool_calls o finish_reason terminal -> terminar
        if not result.tool_calls or result.finish_reason in _TERMINAL_REASONS:
            break

        # Cap defensivo: ejecutar a lo sumo MAX_CALLS_PER_TURN por turno. Las
        # extra se descartan; el assistant message refleja SOLO las que se van a
        # ejecutar para mantener la correlacion assistant/tool del parser hermes.
        calls_this_turn = list(result.tool_calls[:MAX_CALLS_PER_TURN])

        # Agregar turno del assistant al historial CON tool_calls preservado
        # (necesario para multi-turno correcto con Qwen/hermes parser).
        messages.append(
            ChatMessage(
                role="assistant",
                content=result.text or None,
                tool_calls=calls_this_turn,
            )
        )

        # Ejecutar cada tool call y acumular en actions + historial.
        tool_call: ToolCall
        for tool_call in calls_this_turn:
            tool_result = await _execute_anywhere(tool_call.name, tool_call.arguments, registries)
            actions.append(
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result": tool_result,
                }
            )
            # Cap de bytes ANTES de inyectar al historial del LLM (defensa en profundidad):
            # un resultado anormalmente grande NO inunda el context window. Si excede el
            # tope, el modelo recibe un ``tool_error`` (no el payload gigante).
            content = json.dumps(tool_result, ensure_ascii=False)
            if len(content.encode("utf-8")) > TOOL_RESULT_MAX_BYTES:
                too_large = tool_error(
                    "result_too_large", f"resultado de {tool_call.name} demasiado grande"
                )
                content = json.dumps(too_large, ensure_ascii=False)
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=content,
                )
            )
    else:
        # Guard agotado sin converger: el modelo nunca produjo una respuesta final en
        # lenguaje natural (tipicamente loopeo llamando tools, p.ej. qwen reintentando un
        # stub). Se marca el sentinel 'max_iterations' (honesto, no un 'stop' real). El
        # rescate del texto vacio se hace abajo, COMPARTIDO con el corte temprano.
        last_finish_reason = "max_iterations"

    # Rescate de respuesta vacia tras accionar tools (gotcha MEDIDO con qwen real): el
    # modelo puede cortar con finish_reason terminal ('stop') y content VACIO DESPUES de
    # ejecutar una tool (p.ej. agendar) — o agotar el guard. En ambos casos hay acciones
    # ejecutadas pero NO una confirmacion en lenguaje natural, y el usuario veria el
    # fallback generico (lee como error aunque la accion SI ocurrio). Forzamos UNA
    # completion final SIN tools (un unico shot, sin tools que llamar -> no loopea) para
    # que el modelo confirme lo accionado. Si la forzada vuelve con texto, su
    # finish_reason real reemplaza al terminal-vacio / al sentinel 'max_iterations'
    # (telemetria honesta); si vuelve vacia, cae al fallback de abajo (no empeora el caso
    # previo). Cualquier LlmError de esta llamada propaga al caller (route), que degrada.
    # Se gatea en ``actions`` (no en ``not last_text`` a secas) para no forzar una segunda
    # vuelta ante una respuesta conversacional normal que legitimamente vino vacia.
    if not last_text and actions:
        forced = await llm_client.complete(
            model=served_name,
            messages=messages,
            tools=None,
            thinking=thinking,
        )
        last_text = forced.text
        if forced.reasoning:
            reasoning_parts.append(forced.reasoning)
        if last_text:
            last_finish_reason = forced.finish_reason

    final_text = last_text if last_text else fallback_text
    reasoning = "".join(reasoning_parts) or None
    return ToolLoopResult(
        text=final_text,
        actions=actions,
        finish_reason=last_finish_reason,
        reasoning=reasoning,
    )
