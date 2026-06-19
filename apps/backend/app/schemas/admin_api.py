"""Wrappers de respuesta de la API ``/v1/admin/audit`` (NO sagrados).

Envelope de paginación del audit del panel admin. ``AdminAuditRow`` es la vista
**soberana** de ``audit_log``: **omite ``record_hash`` y ``target_id`` del schema**
(no solo del render) — el SELECT del endpoint tampoco los trae. Así la cadena de
integridad y la estructura interna del moat nunca filtran al panel (regla #4).

Separación deliberada (igual que ``session_api.py`` / ``memory_api.py``): los DTOs de
métricas viven en ``app/schemas/admin.py`` y el envelope de paginación vive acá.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.schemas.base import YnaraBaseModel
from app.schemas.chat import CHAT_TEXT_MAX_LENGTH


class AdminAuditRow(YnaraBaseModel):
    """Fila exponible de ``audit_log`` (SIN ``record_hash``, SIN ``target_id``).

    Campos exponibles del audit log per-user: metadata de la operación + su modo/modelo
    de origen + ``sensitive``. NUNCA incluye ``record_hash`` (cadena de integridad) ni
    ``target_id`` (apunta a memoria interna): ambos están ausentes del schema a propósito.
    """

    id: UUID
    created_at: datetime
    operation: AuditOperation
    target_layer: MemoryLayer
    origin_mode: Mode | None
    origin_model: LlmModel | None
    origin_tool: str | None
    sensitive: bool


class AdminAuditPage(YnaraBaseModel):
    """Página de filas de audit: ``items`` paginados + ``total`` + ``sensitive_pct``.

    ``items`` es la página ``limit``/``offset`` (ordenada por ``created_at`` DESC);
    ``total`` es el conteo COMPLETO que matchea los filtros (no el largo de la página);
    ``sensitive_pct`` es el porcentaje de filas sensibles dentro del total filtrado.
    """

    items: list[AdminAuditRow]
    total: int
    sensitive_pct: float


# ---------------------------------------------------------------------------
# Playground admin (F1 ADR-018): inventario de serving read-only + chat de prueba
# ---------------------------------------------------------------------------
#
# Privacidad (regla #4): el inventario de serving NUNCA expone ``base_url`` ni
# connection strings — solo ``backend`` (fake/vllm), ``served_names``, ``role``,
# ``quant``, etc. El playground no persiste nada y nunca ecoa el payload crudo de
# un ``LlmError`` (el mapeo de errores usa solo ``type(exc).__name__``).


class ServingModelOut(YnaraBaseModel):
    """Estado read-only de un modelo del catálogo de serving (F1 ADR-018).

    Combina el contrato de producto (``ynara.config.json`` -> ``ModelConfig`` +
    ``ServingConfig``) con la salud runtime agregada del cliente LLM. NUNCA lleva
    ``base_url`` ni nada que filtre la topología del serving (regla #4).
    """

    key: str  # key interna ("gemma-4-12b" | "qwen-3.5-9b")
    served_name: str  # alias que se pasa a complete() ("gemma4" | "qwen")
    role: str  # "conversational" | "agent"
    writes_memory: bool
    context_window: int
    max_model_len: int  # cfg.serving.max_model_len[key]
    quantization: str  # perfil de serving ("awq_marlin")
    tool_parser: str  # "gemma4" | "hermes"
    healthy: bool  # serves_model(served_name) ∧ health agregada
    default_thinking: bool  # False conversational, True agent (gotcha Gemma, ADR-012 D4)


class ServingOut(YnaraBaseModel):
    """Estado read-only del serving completo (F1 ADR-018).

    Config estática (backend, timeout, embedder/reranker) + salud runtime. Sin
    secretos: NO ``base_url``, NO connection strings. La UI usa ``is_real`` para
    advertir "serving real no disponible" cuando el backend es el Fake.
    """

    backend: str  # settings.llm_backend: "fake" | "vllm"
    is_real: bool  # _wants_real_llm(settings)
    serving_healthy: bool  # await llm_client.health().healthy
    request_timeout_s: float  # cfg.serving.request_timeout_s (120)
    low_perf_available: bool  # True con serving real (preset per-request); False si fake
    models: list[ServingModelOut]
    embedder: str  # settings.embedding_model ("bge-m3")
    reranker: str  # settings.reranker_model ("bge-reranker-v2-m3")


class PlaygroundParams(YnaraBaseModel):
    """Params per-request del playground. ``low_perf`` activa el preset de bajo
    rendimiento (overridea ``max_tokens``/``temperature``/``thinking``)."""

    max_tokens: int = Field(default=1024, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    low_perf: bool = False


class PlaygroundIn(YnaraBaseModel):
    """Body de ``POST /v1/admin/playground``: completion ad-hoc aislada (F1 ADR-018).

    ``model`` es el ``served_name`` ("gemma4"|"qwen"), validado contra el catálogo.
    ``mode`` opcional: si viene (y no hay ``system_prompt`` crudo) se usa
    ``load_prompt(mode)`` como system. ``thinking`` ``None`` -> default por role.
    """

    model: str
    mode: str | None = None
    message: str = Field(min_length=1, max_length=CHAT_TEXT_MAX_LENGTH)
    system_prompt: str | None = None
    params: PlaygroundParams = Field(default_factory=PlaygroundParams)
    thinking: bool | None = None


class TraceStep(YnaraBaseModel):
    """Un paso observable del lifecycle de la completion (Fase A, trace del playground).

    NO lleva payloads sensibles: ni el body crudo del request al serving, ni
    ``base_url``/connection strings, ni el system prompt, ni ``str(exc)`` (regla #4).
    Solo metadata derivada de params públicos + el ``CompletionResult``.
    """

    name: str  # "request" | "thinking" | "completion"
    detail: str  # texto humano: "qwen · max_tokens=256 · temp=0.2"
    duration_ms: float | None = None  # hoy solo el step "completion" lo trae


class PlaygroundOut(YnaraBaseModel):
    """Respuesta del playground: el ``CompletionResult`` crudo + el thinking efectivo.

    Fase A (trace del playground, aditivo, ADR-018): ``text`` viaja **limpio** (sin el
    bloque ``<think>...</think>``), el razonamiento crudo va aparte en ``thinking``
    (``None`` si el modelo no emitió uno) y ``trace`` lleva los pasos observables del
    lifecycle (request/thinking/completion). Sigue siendo un ``complete()`` directo
    (sin tool-loop): el thinking es el del mismo probe crudo.
    """

    text: str
    finish_reason: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    thinking_used: bool  # el thinking efectivo aplicado (para mostrar en UI)
    # --- Fase A: trace + thinking separado ---
    thinking: str | None = None  # el <think>...</think> separado de text, o None
    trace: list[TraceStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Playground agente observado (Fase B ADR-019): tool-loop real, cero efecto
# ---------------------------------------------------------------------------
#
# Privacidad (regla #4): igual que el probe crudo, este path NUNCA expone
# ``base_url``/connection strings ni ecoa el payload de un ``LlmError``. El
# ``result`` de cada tool es el dict que devuelve el stub (``not_wired``) o el
# error estructurado de la tool (``{"error": {"code", "message"}}``) — metadata
# observable de tools sin efecto, nunca contenido descifrado ni datos de usuario.


class ToolCallOut(YnaraBaseModel):
    """Una tool call OBSERVADA del tool-loop (Fase B ADR-019).

    Espeja un elemento de ``actions`` de ``run_tool_loop``: la tool que el modelo
    decidió llamar (``name``), con qué argumentos (``arguments``, ya parseados a
    dict) y qué devolvió (``result``, serializado a JSON string para que el wire
    sea estable sin importar el shape del dict de la tool). En este endpoint todas
    las tools son stubs ``not_wired`` (cero efecto) o caen en ``unknown_tool``.
    """

    id: str  # id de la tool call (correlación con el turno assistant)
    name: str  # ``namespace.action`` (ej. "calendar.create_event")
    arguments: dict[str, object]  # args de la call, ya parseados de JSON a dict
    result: str  # el dict de resultado de la tool, serializado a JSON


class PlaygroundAgentOut(YnaraBaseModel):
    """Respuesta del playground agente observado (Fase B ADR-019).

    Corre el tool-loop real del modelo elegido pero con ``registries=(default_
    registry(), None)`` (sin ``memory_registry`` → imposible tocar la DB): las 4
    tools default son stubs ``not_wired`` y cualquier ``memory.*`` cae en
    ``unknown_tool``. ``actions`` es la traza de tool calls observadas, en orden
    de ejecución. ``text`` es la respuesta final del modelo; ``finish_reason`` el
    del último ``CompletionResult`` (o ``"max_iterations"`` si se agotó el guard).
    """

    text: str
    finish_reason: str
    model_name: str
    actions: list[ToolCallOut] = Field(default_factory=list)
