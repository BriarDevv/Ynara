import { z } from "zod";

/**
 * Contratos del Playground admin (ADR-018 F1, blueprint §2).
 *
 * Espejo Zod EXACTO de los Pydantic del backend (snake_case), para validar las
 * respuestas en el borde igual que el resto del panel: si el backend devuelve un
 * shape inesperado, falla acá y no en el render. En dev el fetch lo intercepta
 * MSW (`servingFixture`/`playgroundEcho`), que parsean su propio fixture contra
 * estos mismos schemas.
 *
 * Dos superficies:
 *  - `ServingOut` — estado read-only del serving (`GET /v1/admin/serving`). Sin
 *    secretos: NO trae `base_url` ni connection strings (regla #4); a lo sumo
 *    host, que F1 ni siquiera expone.
 *  - `PlaygroundIn`/`PlaygroundOut` — completion ad-hoc **sync** (no SSE)
 *    (`POST /v1/admin/playground`), aislada de memoria/tools/sesión.
 */

/** Un modelo del catálogo de serving (estático del config + health runtime). */
export const ServingModelOut = z.object({
  /** Key interna del modelo (`"gemma-4-12b"` | `"qwen-3.5-9b"`). */
  key: z.string(),
  /** Nombre servido, lo que se pasa a `complete()` (`"gemma4"` | `"qwen"`). */
  served_name: z.string(),
  role: z.enum(["conversational", "agent"]),
  writes_memory: z.boolean(),
  context_window: z.number(),
  /** `cfg.serving.max_model_len[key]`. */
  max_model_len: z.number(),
  /** Perfil de cuantización (`"awq_marlin"`); en Ollama se valida, no se pasa. */
  quantization: z.string(),
  tool_parser: z.string(),
  /** `serves_model(served_name)` ∧ health agregada. */
  healthy: z.boolean(),
  /** Default por role: `False` conversational / `True` agent (gotcha Gemma). */
  default_thinking: z.boolean(),
});
export type ServingModelOutT = z.infer<typeof ServingModelOut>;

/** Estado read-only del serving. Sin secretos (regla #4). */
export const ServingOut = z.object({
  backend: z.enum(["fake", "vllm"]),
  /** `_wants_real_llm(settings)`: la UI lo usa para advertir "serving fake". */
  is_real: z.boolean(),
  /** `await llm_client.health().healthy`. */
  serving_healthy: z.boolean(),
  request_timeout_s: z.number(),
  /** `True` siempre (preset per-request); `False` si `backend=fake`. */
  low_perf_available: z.boolean(),
  models: z.array(ServingModelOut),
  embedder: z.string(),
  reranker: z.string(),
});
export type ServingOutT = z.infer<typeof ServingOut>;

/** Params de generación per-request. `low_perf` pisa max_tokens/temp/thinking. */
export const PlaygroundParams = z.object({
  max_tokens: z.number().int().min(1).max(4096).default(1024),
  temperature: z.number().min(0).max(2).default(0.7),
  low_perf: z.boolean().default(false),
});
export type PlaygroundParamsT = z.infer<typeof PlaygroundParams>;

/** Body del completion ad-hoc. `message` ≤ 4000 (= CHAT_TEXT_MAX_LENGTH). */
export const PlaygroundIn = z.object({
  /** `served_name` — validado contra el catálogo en el server (422 si no). */
  model: z.string(),
  mode: z.string().nullable().optional(),
  message: z.string().min(1).max(4000),
  system_prompt: z.string().nullable().optional(),
  params: PlaygroundParams.default({}),
  /** Override manual; `null` → default por role. */
  thinking: z.boolean().nullable().optional(),
});
export type PlaygroundInT = z.infer<typeof PlaygroundIn>;

/**
 * Un paso observable del lifecycle de la completion (Fase A del inspector,
 * blueprint §2). Espejo del `TraceStep` Pydantic: solo metadata derivada del
 * `CompletionResult`, NUNCA payloads sensibles (`base_url`, system prompt
 * completo ni `str(exc)`), regla #4.
 *
 *  - `name`: id del nodo (`"request" | "thinking" | "completion"`).
 *  - `detail`: texto humano ya armado en el server (`"qwen · max_tokens=256"`).
 *  - `duration_ms`: solo el step `completion` lo trae hoy; el resto es `null`.
 */
export const TraceStep = z.object({
  name: z.string(),
  detail: z.string(),
  duration_ms: z.number().nullable().optional(),
});
export type TraceStepT = z.infer<typeof TraceStep>;

/** Respuesta del turno (sync). Métricas con `tabular-nums` en la UI. */
export const PlaygroundOut = z.object({
  text: z.string(),
  finish_reason: z.string(),
  model_name: z.string(),
  prompt_tokens: z.number(),
  completion_tokens: z.number(),
  latency_ms: z.number(),
  /** El thinking efectivo aplicado (para mostrar en UI). */
  thinking_used: z.boolean(),
  /**
   * El `<think>…</think>` separado del `text` (Fase A). `null`/ausente cuando el
   * modelo no expuso pensamiento o el thinking estuvo apagado. Si `thinking_used`
   * es `true` pero esto viene `null`, el inspector muestra "aplicado, no expuesto".
   */
  thinking: z.string().nullable().optional(),
  /**
   * Timeline de pasos del request (Fase A). Vacío en respuestas legacy sin
   * inspector; el `.default([])` lo normaliza para que el front nunca lea
   * `undefined`.
   */
  trace: z.array(TraceStep).default([]),
});
export type PlaygroundOutT = z.infer<typeof PlaygroundOut>;
