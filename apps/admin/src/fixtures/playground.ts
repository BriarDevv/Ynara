import {
  PlaygroundAgentOut,
  type PlaygroundAgentOutT,
  type PlaygroundInT,
  PlaygroundOut,
  type PlaygroundOutT,
  ServingModelOut,
  type ServingModelOutT,
  ServingOut,
  type ServingOutT,
} from "@/features/playground/schemas";

/**
 * Fixtures del Playground (ADR-018 §3 / blueprint §3 "Handlers MSW").
 *
 * `servingFixture` trae los DOS modelos reales del catálogo (gemma4
 * conversational + qwen agent) sobre un backend `vllm` real y sano, para que el
 * dev vea la pantalla en su estado feliz. `playgroundEcho` devuelve un turno
 * determinista que refleja modelo/low_perf/thinking efectivo (mismo cálculo que
 * el server) con latencia simulada por el handler. `playgroundAgentEcho` devuelve
 * un turno de modo agente con 2 tool-calls de ejemplo (Fase B).
 *
 * Cada fixture se devuelve **parseado por su propio Zod**, igual que el resto de
 * los fixtures del panel: el `parse` es la última garantía de que lo que sale por
 * la red cumple el contrato que el hook va a re-parsear.
 */

/** Los dos modelos reales del catálogo de serving (ADR-013/014). */
const GEMMA: ServingModelOutT = ServingModelOut.parse({
  key: "gemma-4-12b",
  served_name: "gemma4",
  role: "conversational",
  writes_memory: false,
  context_window: 128000,
  max_model_len: 8192,
  quantization: "awq_marlin",
  tool_parser: "gemma4",
  healthy: true,
  default_thinking: false,
});

const QWEN: ServingModelOutT = ServingModelOut.parse({
  key: "qwen-3.5-9b",
  served_name: "qwen",
  role: "agent",
  writes_memory: true,
  context_window: 262144,
  max_model_len: 32768,
  quantization: "awq_marlin",
  tool_parser: "hermes",
  healthy: true,
  default_thinking: true,
});

/**
 * `GET /v1/admin/serving` — estado feliz: backend vllm real y sano, los 2
 * modelos del catálogo healthy, embedder/reranker cargados. Sin secretos.
 */
export function servingFixture(): ServingOutT {
  const data: ServingOutT = {
    backend: "vllm",
    is_real: true,
    serving_healthy: true,
    request_timeout_s: 120,
    low_perf_available: true,
    models: [GEMMA, QWEN],
    embedder: "bge-m3",
    reranker: "bge-reranker-v2-m3",
  };
  return ServingOut.parse(data);
}

/**
 * Variante FAKE para probar el banner ámbar + el empty-state de "serving fake"
 * (sin generación real). Cambiar el handler de `servingFixture` por esta en
 * `fixtures/handlers.ts` para verificar la rama `is_real=false`:
 *
 * ```ts
 * export function servingFixtureFake(): ServingOutT {
 *   return ServingOut.parse({ ...servingFixture(), backend: "fake", is_real: false,
 *     serving_healthy: true, low_perf_available: false });
 * }
 * ```
 */

/** Mapea un modelo servido a su `default_thinking` (gotcha Gemma del §2.2). */
function defaultThinkingFor(servedName: string): boolean {
  return servedName === "qwen";
}

/**
 * Thinking efectivo, mismo cálculo que el server (§2.2 pasos 3-4): `low_perf`
 * lo fuerza a `false`; un override manual gana sobre el default por role; si no,
 * el default por role.
 */
function effectiveThinking(body: PlaygroundInT): boolean {
  if (body.params.low_perf) return false;
  if (body.thinking != null) return body.thinking;
  return defaultThinkingFor(body.model);
}

/** Estimación grosera de tokens (≈ 4 chars/token), como en el §3. */
function approxTokens(text: string): number {
  return Math.max(1, Math.round(text.length / 4));
}

/**
 * `<think>…</think>` de ejemplo cuando el thinking efectivo está encendido (el
 * server lo separa del `text` en Fase A). Con thinking apagado el modelo no
 * expone pensamiento → `null`, y el inspector no pinta el bloque colapsable.
 */
function thinkingTextFor(body: PlaygroundInT, thinkingUsed: boolean): string | null {
  if (!thinkingUsed) return null;
  return `<think>\nDesglozo el pedido del operador (${body.model}).\nReúno contexto y decido la respuesta más útil sin tools ni memoria (probe crudo).\n</think>`;
}

/**
 * `POST /v1/admin/playground` — eco determinista: el texto refleja modelo +
 * low_perf, y las métricas (tokens/latencia/thinking) se derivan del body. El
 * delay de "generación" lo agrega el handler MSW, no este fixture.
 *
 * Fase A (blueprint §2): además devuelve el `trace` (3 steps coherentes —
 * request → thinking → completion) y el `thinking` separado (un `<think>` de
 * ejemplo con thinking on; `null` con thinking off), para que el inspector se
 * vea en dev sobre los mocks.
 */
export function playgroundEcho(body: PlaygroundInT): PlaygroundOutT {
  const thinkingUsed = effectiveThinking(body);
  const text = `Echo [${body.model}, low_perf=${body.params.low_perf}, thinking=${thinkingUsed}]: ${body.message}`;
  const promptTokens = approxTokens(body.message);
  const completionTokens = approxTokens(text);
  const latencyMs = 800;

  const data: PlaygroundOutT = {
    text,
    finish_reason: "stop",
    model_name: body.model,
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    latency_ms: latencyMs,
    thinking_used: thinkingUsed,
    thinking: thinkingTextFor(body, thinkingUsed),
    // Mismo orden y semántica que el server (blueprint §2): metadata pública,
    // sin secretos (regla #4). El step `request` refleja el preset low_perf.
    trace: [
      {
        name: "request",
        detail:
          `${body.model} · max_tokens=${body.params.max_tokens} · temp=${body.params.temperature}` +
          (body.params.low_perf ? " · preset low_perf" : ""),
      },
      { name: "thinking", detail: thinkingUsed ? "on" : "off" },
      {
        name: "completion",
        detail: `stop · ${promptTokens + completionTokens} tok`,
        duration_ms: latencyMs,
      },
    ],
  };
  return PlaygroundOut.parse(data);
}

/**
 * `POST /v1/admin/playground/agent` — eco agente determinista (Fase B,
 * blueprint §4): simula el tool-loop del modelo con 2 tool-calls de ejemplo
 * (stubs `not_wired`, cero efecto real) para que el modo agente se vea en dev.
 *
 * - `calendar.create_event`: el modelo pide crear un evento con args derivados
 *   del mensaje; el stub devuelve `not_wired` (tool no cableada en dev).
 * - `reminder.set`: el modelo pide un recordatorio; ídem `not_wired`.
 *
 * El delay de "generación" lo agrega el handler MSW, no este fixture.
 * Los IDs de call-id son deterministas para que el fixture sea estable en tests.
 */
export function playgroundAgentEcho(body: PlaygroundInT): PlaygroundAgentOutT {
  const data: PlaygroundAgentOutT = {
    text: `[Modo agente · ${body.model}] Procesé tu pedido con el tool-loop observado. Llamé calendar.create_event y reminder.set — ambas devuelven not_wired en dev (sin efecto real). Respuesta: "${body.message}"`,
    finish_reason: "stop",
    model_name: body.model,
    // trace vacío: el loop no expone TraceSteps por iteración (limitación ADR).
    trace: [],
    actions: [
      {
        id: "call-001",
        name: "calendar.create_event",
        // JSON crudo de args: lo que el modelo emitió en la tool-call.
        arguments: JSON.stringify(
          {
            title: body.message.slice(0, 60),
            start: "2026-07-01T10:00:00Z",
            end: "2026-07-01T11:00:00Z",
          },
          null,
          2,
        ),
        result: "not_wired",
      },
      {
        id: "call-002",
        name: "reminder.set",
        arguments: JSON.stringify(
          {
            message: body.message.slice(0, 60),
            at: "2026-07-01T09:30:00Z",
          },
          null,
          2,
        ),
        result: "not_wired",
      },
    ],
  };
  return PlaygroundAgentOut.parse(data);
}
