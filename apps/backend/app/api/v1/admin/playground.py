"""Playground admin (ADR-018/019): inventario de serving + chat de prueba aislado.

Superficie SEPARADA de las métricas: el operador prueba los modelos crudos sin tocar
datos reales. Gate ``CurrentAdmin``.

Privacidad (regla #4) — invariantes NO re-litigables:
(1) NUNCA se expone ``base_url`` ni connection strings del serving (host/creds):
    ``ServingOut`` ni siquiera tiene el campo. Solo backend (fake/vllm), served_names,
    role, quant, etc.
(2) El playground NO persiste nada (sin ``DbSession`` en la firma -> cero
    ``ChatSession``/``conversation_turns``/``episodic``/``consolidate_turn``).
(3) NUNCA se ecoa el body crudo de un ``LlmError``: el mapeo de errores usa solo
    ``type(exc).__name__``, jamás ``str(exc)`` con payload.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.deps import CurrentAdmin, get_llm_client
from app.core.llm_protocol import LLMClientProtocol
from app.enums import Mode
from app.llm.clients.factory import _wants_real_llm
from app.llm.config import ModelConfig, load_llm_config
from app.llm.errors import (
    LlmBadRequestError,
    LlmContextOverflowError,
    LlmError,
    LlmOverloadedError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelNotServedError,
)
from app.llm.prompts.loader import load_prompt
from app.llm.schemas import ChatMessage
from app.llm.text_utils import split_thinking
from app.schemas.admin_api import (
    PlaygroundAgentOut,
    PlaygroundIn,
    PlaygroundOut,
    ServingModelOut,
    ServingOut,
    ToolCallOut,
    TraceStep,
)

router = APIRouter()

# Preset "bajo rendimiento" (F1 ADR-018): topes per-request que materializan el
# modo de bajo rendimiento (menos VRAM-time/latencia). Pisan los params del body.
_LOW_PERF_MAX_TOKENS = 256
_LOW_PERF_TEMPERATURE = 0.2
_LOW_PERF_TIMEOUT_S = 30.0

# System prompt neutro por default cuando el operador no manda ``system_prompt`` ni
# ``mode`` (el playground es un probe del modelo crudo, sin la voz de producto).
_PLAYGROUND_DEFAULT_SYSTEM = "Sos un asistente útil. Respondé de forma concisa."


class _ResolvedPlayground(NamedTuple):
    """Resultado de resolver los pasos 1-5 comunes a los 3 handlers del playground.

    Inmutable (NamedTuple): centraliza el lookup del modelo, el thinking efectivo, el
    preset low_perf y el system prompt ya construido como ``messages``. Cada handler
    consume solo lo que necesita: el probe sync/stream usa ``max_tokens``/``temperature``/
    ``timeout_s``; el tool-loop agente los ignora (el loop no toma params per-request).
    """

    model_cfg: ModelConfig
    thinking: bool
    max_tokens: int
    temperature: float
    timeout_s: float | None
    messages: list[ChatMessage]


def _resolve_playground_request(body: PlaygroundIn) -> _ResolvedPlayground:
    """Centraliza los pasos 1-5 compartidos por los 3 handlers (DRY, behavior-preserving).

    Mismos chequeos y MISMO orden que tenía cada handler inline:
    (1) lookup del ``served_name`` en el catálogo -> 422 "modelo no servido";
    (2) backend fake sin serving real -> 409 "serving real no disponible";
    (3) thinking efectivo: override del body > default por role (True solo si ``agent``);
    (4) preset low_perf: pisa max_tokens/temp/thinking + fija timeout (el agente solo
        lee ``thinking``, ignora los params -> el efecto observable es idéntico);
    (5) system prompt: override crudo > ``load_prompt(mode)`` > default neutro, con 422
        "modo desconocido" si el ``mode`` no resuelve.

    Las ``HTTPException`` (422/409) suben tal cual al caller -> mismos códigos/mensajes.
    """
    settings = get_settings()
    cfg = load_llm_config()

    # 1) Validar el modelo elegido contra el catálogo de served_names.
    models_by_served = {m.served_name: m for m in cfg.models.values()}
    model_cfg = models_by_served.get(body.model)
    if model_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="modelo no servido"
        )

    # 2) Sin serving real (backend fake) no hay generación: 409 ANTES de llamar al
    #    cliente (el Fake del lifespan no tiene respuestas encoladas -> evita el 500).
    if not _wants_real_llm(settings):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="serving real no disponible"
        )

    # 3) Thinking efectivo: override manual del body, si no el default por role
    #    (False conversational / True agent; gotcha Gemma+thinking -> content vacío).
    thinking = body.thinking if body.thinking is not None else model_cfg.role == "agent"

    # 4) Params efectivos; el preset low_perf pisa max_tokens/temp/thinking + timeout.
    max_tokens = body.params.max_tokens
    temperature = body.params.temperature
    timeout_s: float | None = None
    if body.params.low_perf:
        max_tokens = min(_LOW_PERF_MAX_TOKENS, body.params.max_tokens)
        temperature = min(_LOW_PERF_TEMPERATURE, body.params.temperature)
        thinking = False
        timeout_s = _LOW_PERF_TIMEOUT_S

    # 5) System prompt: override crudo > load_prompt(mode) > default neutro.
    system_content = body.system_prompt or _PLAYGROUND_DEFAULT_SYSTEM
    if body.system_prompt is None and body.mode is not None:
        try:
            system_content = load_prompt(Mode(body.mode))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="modo desconocido"
            ) from exc

    messages = [
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user", content=body.message),
    ]

    return _ResolvedPlayground(
        model_cfg=model_cfg,
        thinking=thinking,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_s=timeout_s,
        messages=messages,
    )


@router.get("/admin/serving", response_model=ServingOut, status_code=200)
async def admin_serving(
    admin_id: CurrentAdmin,
    llm_client: Annotated[LLMClientProtocol, Depends(get_llm_client)],
) -> ServingOut:
    """Inventario read-only del serving: config estática + salud runtime agregada.

    Combina ``load_llm_config()`` + ``settings`` con una sola ``llm_client.health()``.
    NUNCA expone ``base_url`` ni connection strings (regla #4): solo backend
    (fake/vllm), served_names, role, quant, tool_parser, etc. Con backend fake el
    Fake reporta sano (``serving_healthy=True``) pero ``is_real``/``low_perf_available``
    son ``False`` para que la UI advierta que no hay generación real.
    """
    settings = get_settings()
    cfg = load_llm_config()
    is_real = _wants_real_llm(settings)

    # Una sola llamada de health agregada; se combina con serves_model por modelo.
    health = await llm_client.health()

    models = [
        ServingModelOut(
            key=model.key,
            served_name=model.served_name,
            role=model.role,
            writes_memory=model.writes_memory,
            context_window=model.context_window,
            max_model_len=cfg.serving.max_model_len[model.key],
            quantization=cfg.serving.quantization,
            tool_parser=cfg.serving.tool_parsers[model.key],
            healthy=health.healthy and llm_client.serves_model(model.served_name),
            default_thinking=model.role == "agent",
        )
        for model in cfg.models.values()
    ]

    return ServingOut(
        backend=settings.llm_backend,
        is_real=is_real,
        serving_healthy=health.healthy,
        request_timeout_s=float(cfg.serving.request_timeout_s),
        low_perf_available=is_real,
        models=models,
        embedder=settings.embedding_model,
        reranker=settings.reranker_model,
    )


def _map_llm_error(exc: LlmError) -> HTTPException:
    """Mapea un ``LlmError`` a un ``HTTPException`` SIN ecoar el payload (regla #4).

    El ``detail`` es solo el nombre de la clase de la excepción (``type(exc).__name__``),
    nunca ``str(exc)`` (que podría llevar detalle técnico del request/respuesta).
    Transitorios -> 503/504; permanentes -> 422; genérico -> 502.
    """
    if isinstance(exc, LlmTimeoutError):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, (LlmUnavailableError, LlmOverloadedError)):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, (LlmContextOverflowError, LlmBadRequestError, ModelNotServedError)):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=code, detail=type(exc).__name__)


@router.post("/admin/playground", response_model=PlaygroundOut, status_code=200)
async def admin_playground(
    body: PlaygroundIn,
    admin_id: CurrentAdmin,
    llm_client: Annotated[LLMClientProtocol, Depends(get_llm_client)],
) -> PlaygroundOut:
    """Completion ad-hoc aislada contra un modelo elegido (F1 ADR-018).

    Llama ``llm_client.complete()`` DIRECTO (sin ``route()``/``run_tool_loop()``, sin
    ``DbSession``): cero sesión/memoria/tools. Valida el ``served_name`` contra el
    catálogo (422 si no se sirve), rechaza el backend fake (409, evita la
    ``AssertionError`` del Fake del lifespan), aplica el preset low_perf si se pidió y
    mapea la familia ``LlmError`` a status sin ecoar el payload (regla #4).
    """
    # 1-5) Resolución compartida: lookup/422 + 409 fake + thinking + low_perf + prompt.
    resolved = _resolve_playground_request(body)
    model_cfg = resolved.model_cfg
    thinking = resolved.thinking
    max_tokens = resolved.max_tokens
    temperature = resolved.temperature

    # 6) Llamada directa al cliente; 7) mapear LlmError a status sin ecoar payload.
    try:
        result = await llm_client.complete(
            model=model_cfg.served_name,
            messages=resolved.messages,
            tools=None,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking=thinking,
            timeout_s=resolved.timeout_s,
        )
    except LlmError as exc:
        raise _map_llm_error(exc) from exc

    # 8) Pensamiento del turno: el canal ``reasoning`` separado (qwen via Ollama lo
    #    manda en ``message.reasoning``, no inline) tiene precedencia; si el modelo
    #    en cambio embebió <think>...</think> en el ``content`` (vLLM sin
    #    reasoning-parser) lo separamos de ahí. El ``text`` queda siempre limpio.
    clean_text, inline_thinking = split_thinking(result.text)
    thinking_text = result.reasoning or inline_thinking

    # 9) Trace observable del lifecycle (Fase A, aditivo). PRIVACIDAD (regla #4):
    #    los ``detail`` solo concatenan params PÚBLICOS (los que el operador ya mandó)
    #    + metadata del ``CompletionResult``. NUNCA base_url, system prompt ni str(exc).
    trace = [
        TraceStep(
            name="request",
            detail=f"{model_cfg.served_name} · max_tokens={max_tokens} · temp={temperature}"
            + (" · preset low_perf" if body.params.low_perf else ""),
        ),
        TraceStep(name="thinking", detail="on" if thinking else "off"),
        TraceStep(
            name="completion",
            detail=f"{result.finish_reason} · "
            f"{result.prompt_tokens + result.completion_tokens} tok",
            duration_ms=result.latency_ms,
        ),
    ]

    return PlaygroundOut(
        text=clean_text,
        finish_reason=result.finish_reason,
        model_name=result.model_name,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=result.latency_ms,
        thinking_used=thinking,
        thinking=thinking_text,
        trace=trace,
    )


def _sse_event(event: str, data: dict[str, Any]) -> bytes:
    """Serializa un evento SSE (``event:`` + ``data:`` JSON + ``\\n\\n``).

    ``ensure_ascii=False`` para no escapar los acentos del delta del modelo. El
    payload NUNCA lleva secretos (base_url, system prompt ni ``str(exc)``): solo
    el delta de texto y, en ``done``, métricas derivadas del stream (regla #4).
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


@router.post("/admin/playground/stream")
async def admin_playground_stream(
    body: PlaygroundIn,
    admin_id: CurrentAdmin,
    llm_client: Annotated[LLMClientProtocol, Depends(get_llm_client)],
) -> StreamingResponse:
    """Completion ad-hoc en STREAMING (SSE) — gemela de ``/admin/playground``.

    Mismo aislamiento (sin ``DbSession``, sin sesión/memoria/tools) y mismas
    validaciones que el probe sync, pero emite la generación token-por-token vía
    Server-Sent Events para que el panel pinte el texto en vivo + tokens/seg. Las
    validaciones (422 modelo no servido, 409 backend fake, 422 modo desconocido)
    corren ANTES de construir el ``StreamingResponse`` -> salen como HTTP normal,
    no como SSE.

    Contrato de eventos (consumido por el panel):
      - ``token``     -> ``{"delta": <str>}`` por cada chunk de TEXTO del modelo.
      - ``reasoning`` -> ``{"delta": <str>}`` por cada fragmento del canal de
        razonamiento SEPARADO (qwen thinking; APARTE del ``content``). Se pinta en
        vivo y el ``thinking`` final del ``done`` lo trae acumulado. NO cuenta como
        ``completion_token`` (esos son solo los del texto de respuesta).
      - ``done``  -> métricas finales (finish_reason, model_name, completion_tokens,
        latency_ms, tokens_per_second, thinking_used, thinking separado).
      - ``error`` -> ``{"code": "stream_error", "message": <neutro>}`` ante
        cualquier ``LlmError`` (NUNCA el ``str(exc)``, regla #4).

    ``completion_tokens`` se cuenta como chunks con delta no vacío (granularidad
    real del stream del modelo) y ``tokens_per_second`` se deriva con la latencia
    medida en el server. El stream NO trae ``usage`` -> sin ``prompt_tokens``.
    """
    # 1-5) Resolución compartida (idéntica al probe sync): lookup/422 + 409 fake +
    #    thinking + low_perf + prompt. Las validaciones suben como HTTP normal acá,
    #    ANTES de construir el StreamingResponse (no como SSE).
    resolved = _resolve_playground_request(body)
    max_tokens = resolved.max_tokens
    temperature = resolved.temperature
    timeout_s = resolved.timeout_s
    messages = resolved.messages
    # Snapshot a primitivos: el generator cierra sobre valores ya resueltos (no
    # sobre el request/Depends), mismo cuidado que /chat/stream.
    served_name = resolved.model_cfg.served_name
    effective_thinking = resolved.thinking

    async def _gen() -> AsyncIterator[bytes]:
        started = time.perf_counter()
        parts: list[str] = []
        reasoning_parts: list[str] = []
        completion_tokens = 0
        finish_reason = "stop"
        try:
            async for chunk in llm_client.stream(
                model=served_name,
                messages=messages,
                tools=None,
                max_tokens=max_tokens,
                temperature=temperature,
                thinking=effective_thinking,
                timeout_s=timeout_s,
            ):
                # Canal de razonamiento (qwen): llega APARTE del content. Se emite en
                # vivo para pintar "qué piensa" mientras pasa; NO suma completion_token.
                if chunk.reasoning_delta:
                    reasoning_parts.append(chunk.reasoning_delta)
                    yield _sse_event("reasoning", {"delta": chunk.reasoning_delta})
                if chunk.delta_text:
                    parts.append(chunk.delta_text)
                    completion_tokens += 1
                    yield _sse_event("token", {"delta": chunk.delta_text})
                if chunk.finish_reason is not None:
                    finish_reason = chunk.finish_reason
        except LlmError:
            # Mensaje NEUTRO (regla #4): nunca el str(exc) ni el payload del error.
            yield _sse_event(
                "error",
                {"code": "stream_error", "message": "No se pudo completar la respuesta"},
            )
            return

        latency_ms = (time.perf_counter() - started) * 1000.0
        tps = completion_tokens / (latency_ms / 1000.0) if latency_ms > 0 else 0.0
        # Pensamiento del turno: el canal ``reasoning`` acumulado (qwen via Ollama)
        # tiene precedencia; si en cambio vino embebido como <think>...</think> en el
        # content (vLLM sin reasoning-parser), lo separamos de ahí.
        _clean, inline_thinking = split_thinking("".join(parts))
        thinking_text = "".join(reasoning_parts) or inline_thinking
        yield _sse_event(
            "done",
            {
                "finish_reason": finish_reason,
                "model_name": served_name,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "tokens_per_second": tps,
                "thinking_used": effective_thinking,
                "thinking": thinking_text,
            },
        )

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Playground agente OBSERVADO (Fase B ADR-019): tool-loop real, cero efecto
# ---------------------------------------------------------------------------
#
# Refina ADR-018: superficie SEPARADA del probe crudo de /playground (que sigue
# vigente). Corre ``run_tool_loop`` real del modelo elegido pero con registries
# que hacen IMPOSIBLE tocar datos reales.
#
# INVARIANTE DE NO-EFECTO (ADR-019 D2, NO negociable): ``registries=(default_
# registry(), None)``. El ``None`` = SIN ``memory_registry`` → ni se construye el
# store → las dos tools con write real (``memory.update``/``memory.delete``) son
# INALCANZABLES por construcción, y cualquier ``memory.*`` cae en ``unknown_tool``
# (observable, cero efecto). Las 4 tools del default (calendar/reminder) son stubs
# ``not_wired``. SIN ``DbSession`` en la firma → cero sesión/memoria/consolidación.


@router.post("/admin/playground/agent", response_model=PlaygroundAgentOut, status_code=200)
async def admin_playground_agent(
    body: PlaygroundIn,
    admin_id: CurrentAdmin,
    llm_client: Annotated[LLMClientProtocol, Depends(get_llm_client)],
) -> PlaygroundAgentOut:
    """Tool-loop OBSERVADO contra un modelo elegido, a cero efecto (Fase B ADR-019).

    Corre ``run_tool_loop`` real (el modelo decide qué tools llamar, paso a paso)
    pero con ``registries=(default_registry(), None)``: sin ``memory_registry``, las
    tools con write son inalcanzables por construcción (invariante de no-efecto,
    ADR-019 D2). Las specs son solo ``calendar`` + ``reminder`` (los 4 stubs
    ``not_wired``). MISMAS validaciones que ``/playground`` (422 modelo no servido,
    409 backend fake) y MISMO mapeo ``LlmError``→status sin ecoar el payload
    (regla #4). SIN ``DbSession``: cero sesión/memoria/consolidación.
    """
    # Importes locales (lazy): la capa tool-loop solo se carga en este path, no
    # en el import del módulo (que es mayormente probes read-only).
    from app.llm.tool_loop import run_tool_loop
    from app.llm.tools.registry import default_registry

    # 1-4) Resolución compartida (igual que /playground): lookup/422 + 409 fake +
    #    thinking (low_perf lo fuerza OFF) + prompt. El tool-loop NO toma
    #    max_tokens/temp/timeout per-request, así que esos campos del resolved se
    #    ignoran: el efecto observable es idéntico al inline previo.
    resolved = _resolve_playground_request(body)
    model_cfg = resolved.model_cfg
    thinking = resolved.thinking
    messages = resolved.messages

    # 5) INVARIANTE DE NO-EFECTO (ADR-019 D2): default_registry() (4 stubs no-op) +
    #    None (SIN memory_registry -> ni se construye el store -> memory.* es
    #    inalcanzable). Specs = solo calendar + reminder (los stubs observables).
    default_reg = default_registry()
    specs = default_reg.specs_for(["calendar", "reminder"])

    # 6) Correr el tool-loop real; 7) mapear LlmError a status sin ecoar payload.
    try:
        text, actions, finish_reason = await run_tool_loop(
            llm_client=llm_client,
            served_name=model_cfg.served_name,
            messages=messages,
            specs=specs,
            registries=(default_reg, None),  # None = SIN memory_registry = imposible escribir DB
            thinking=thinking,
            fallback_text="(sin respuesta)",
        )
    except LlmError as exc:
        raise _map_llm_error(exc) from exc

    # 8) Mapear las actions observadas a ToolCallOut. ``result`` se serializa a JSON
    #    string (wire estable). PRIVACIDAD (regla #4): son dicts de tools sin efecto
    #    (``not_wired`` / ``unknown_tool``), nunca contenido descifrado ni PII.
    observed = [
        ToolCallOut(
            id=str(action["id"]),
            name=str(action["name"]),
            arguments=action["arguments"],  # type: ignore[arg-type]
            result=json.dumps(action["result"], ensure_ascii=False),
        )
        for action in actions
    ]

    return PlaygroundAgentOut(
        text=text,
        finish_reason=finish_reason,
        model_name=model_cfg.served_name,
        actions=observed,
    )
