import { z } from "zod";

import { ModeSchema } from "./modes";

/**
 * Contrato del chat — mirror del endpoint HTTP `/v1/chat(/stream)`.
 *
 * Fuente de verdad: `apps/backend/app/llm/schemas.py` (ChatRequest /
 * ChatResponse / ChatMessage), `apps/backend/app/schemas/session.py`
 * (SessionOut), `apps/backend/docs/ENDPOINTS.md` y las decisiones cerradas en
 * `docs/planning/RESPUESTAS-CONTRATO-CHAT.md` (PR #61).
 *
 * Regla "Pydantic gana, Zod sigue": si el backend cambia el contrato, se
 * corrige este mirror en el mismo PR. El Pydantic ya existe, así que la
 * divergencia es detectable en code review.
 */

/** Límite de longitud del mensaje (techo seguro vs `max_model_len` de Gemma). */
export const CHAT_TEXT_MAX_LENGTH = 4000;

/**
 * Request a `POST /v1/chat` y `POST /v1/chat/stream`.
 *
 * `min(1)` y `max(CHAT_TEXT_MAX_LENGTH)` se adelantan al backend: el Pydantic
 * `ChatRequest.text` hoy es `str` pelado; el `max_length=4000` se cablea en M9
 * (accion #3 de RESPUESTAS-CONTRATO-CHAT). Validar client-side no tiene
 * contra: no mandamos texto vacio ni por encima del techo de Gemma.
 */
export const ChatRequestSchema = z.object({
  text: z.string().min(1).max(CHAT_TEXT_MAX_LENGTH),
  mode: ModeSchema,
  // Pydantic: `str | None = None`. Aceptamos ausente o null (= sesion nueva).
  session_id: z.string().uuid().nullable().optional(),
});
export type ChatRequest = z.infer<typeof ChatRequestSchema>;

/**
 * Un mensaje del historial (formato OpenAI-like, mirror de `ChatMessage`).
 *
 * Pydantic define `content`/`tool_call_id`/`name` como `str | None = None`.
 * Pydantic v2 los serializa como `null` (no los omite), asi que el mirror usa
 * `.nullable().optional()`: acepta el campo ausente, presente con string, o
 * presente con `null` (p. ej. assistant que solo emite tool_calls).
 */
export const ChatMessageSchema = z.object({
  role: z.enum(["system", "user", "assistant", "tool"]),
  content: z.string().nullable().optional(),
  tool_call_id: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

/**
 * Una acción ejecutada por el agente Qwen (tool call CON resultado).
 *
 * `result` es el dict que devuelve `ToolRegistry.execute` (hoy stub
 * `{ status: "not_wired" }`) o `{ error: { code, message } }` si falló. Solo
 * los modos Qwen (productividad, memoria) producen acciones; Gemma → `[]`.
 */
export const ActionSchema = z.object({
  id: z.string(),
  name: z.string(),
  arguments: z.record(z.unknown()),
  result: z.record(z.unknown()),
});
export type Action = z.infer<typeof ActionSchema>;

/** Response de `POST /v1/chat` (no-streaming). */
export const ChatResponseSchema = z.object({
  text: z.string(),
  // Siempre presente (vacío si no hubo acciones), nunca opcional —
  // matchea el default `actions = []` de Pydantic.
  actions: z.array(ActionSchema).default([]),
  session_id: z.string(),
  // `finish_reason` del router: required-pero-nullable, igual que `ended_at`.
  // El Pydantic `ChatHttpResponse.finish_reason: str | None = None` siempre
  // serializa la clave, con `null` cuando el router no lo seteó. A diferencia
  // de `StreamDoneSchema` (el `done` SSE lo coerciona a string no-null), el
  // no-streaming puede venir `null`.
  finish_reason: z.string().nullable(),
});
export type ChatResponse = z.infer<typeof ChatResponseSchema>;

/**
 * Sesión de conversación (mirror COMPLETO de `SessionOut`).
 *
 * `ended_at` es required-pero-nullable en el Pydantic (`datetime | None`), no
 * opcional: la clave siempre viene, con `null` si la sesión sigue abierta.
 */
export const SessionSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  mode: ModeSchema,
  started_at: z.string().datetime({ offset: true }),
  ended_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type Session = z.infer<typeof SessionSchema>;

// --- Eventos del stream SSE (`POST /v1/chat/stream`, ver `sse.ts`) ---

/** `event: token` — un fragmento de texto. El front concatena. */
export const StreamTokenSchema = z.object({
  delta: z.string(),
});
export type StreamToken = z.infer<typeof StreamTokenSchema>;

/** `event: done` — evento terminal, análogo del `ChatResponse` no-streaming. */
export const StreamDoneSchema = z.object({
  session_id: z.string(),
  actions: z.array(ActionSchema).default([]),
  finish_reason: z.string(),
});
export type StreamDone = z.infer<typeof StreamDoneSchema>;

/** `event: error` — algo reventó mid-stream. Sin datos de usuario (regla #4). */
export const StreamErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
});
export type StreamError = z.infer<typeof StreamErrorSchema>;
