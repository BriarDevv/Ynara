import { z } from "zod";

import { ModeSchema } from "./modes";

/**
 * Contrato del dashboard **Hoy** (build-plan Fase E): prioridades del día,
 * sugerencias proactivas y recap del día.
 *
 * Estado actual de los endpoints (junio 2026):
 *  - `/v1/tasks` → **operativo** (backend real, Tanda 1).
 *  - `/v1/suggestions` → **pendiente** (requiere LLM real + agenda; roadmap D2/F).
 *  - `/v1/recap` → **pendiente** (requiere LLM real; roadmap F). Hasta que
 *    existan, los hooks degradan a resultado vacío ante 404 (no error visible).
 *
 * Snake_case y `datetime({ offset: true })` para espejar la convención Pydantic
 * del resto del backend (FastAPI), de modo que al cablear el endpoint real el
 * shape ya coincida ("Pydantic gana, Zod sigue").
 */

// ---------- Prioridades del día (`GET /v1/tasks`) ----------

/** Estado de una tarea: pendiente o hecha (el check del wireframe 06). */
export const TaskStatusSchema = z.enum(["pending", "done"]);
export type TaskStatus = z.infer<typeof TaskStatusSchema>;

/**
 * Una prioridad del día. `scheduled_at` + `duration_min` arman la meta
 * "14:00 · 45 min"; cuando `status` es `done` la meta muestra "completada"
 * (derivado, no un campo aparte). El futuro modelo `Task` del backend sumará
 * campos de auditoría (created_at/updated_at) que no necesitamos en cliente.
 */
export const TaskSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  status: TaskStatusSchema,
  /** Hora agendada (ISO con offset). `null` si la tarea no tiene horario. */
  scheduled_at: z.string().datetime({ offset: true }).nullable(),
  /** Duración estimada en minutos. `null` si no aplica. */
  duration_min: z.number().int().positive().nullable(),
});
export type Task = z.infer<typeof TaskSchema>;

/** Respuesta de `GET /v1/tasks`: las prioridades del día + el total. */
export const TasksResponseSchema = z.object({
  items: z.array(TaskSchema),
  total: z.number().int().nonnegative(),
});
export type TasksResponse = z.infer<typeof TasksResponseSchema>;

/**
 * Body de `PATCH /v1/tasks/{id}`: por ahora sólo togglea el estado (marcar
 * hecha / re-abrir desde el check). Mirror de la rama mínima del futuro
 * `TaskUpdate`.
 */
export const TaskPatchSchema = z.object({
  status: TaskStatusSchema,
});
export type TaskPatch = z.infer<typeof TaskPatchSchema>;

// ---------- Sugerencias (`GET /v1/suggestions`) ----------

/**
 * Una sugerencia proactiva ("Ynara sugiere"): un título y su **porqué** (lo que
 * la hace honesta, no una orden arbitraria). `mode` la tinta y la asocia a un
 * modo; `null` si es transversal. Las genera el LLM real a futuro — hoy son
 * fixtures.
 */
export const SuggestionSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  /** El "porqué" de la sugerencia (subtítulo del wireframe 06/07). */
  why: z.string().min(1),
  /** Modo al que pertenece (para el tint), o `null` si es transversal. */
  mode: ModeSchema.nullable(),
});
export type Suggestion = z.infer<typeof SuggestionSchema>;

/** Respuesta de `GET /v1/suggestions`. */
export const SuggestionsResponseSchema = z.object({
  items: z.array(SuggestionSchema),
});
export type SuggestionsResponse = z.infer<typeof SuggestionsResponseSchema>;

// ---------- Recap del día (`GET /v1/recap`) ----------

/**
 * Recap del día (wireframe 15, CTA "Recap pendiente" del 06). `pending` mientras
 * no se cerró el día; al cerrarlo Ynara devuelve un `headline` editorial y los
 * `highlights` (lo que pasó). Generado por LLM a futuro; mock por ahora.
 */
export const RecapSchema = z.object({
  /** `true` mientras el día no se cerró (muestra el CTA en Hoy). */
  pending: z.boolean(),
  /** Fecha del día al que pertenece el recap (ISO con offset). */
  date: z.string().datetime({ offset: true }),
  /** Frase editorial de cierre (presente sólo si ya se generó). */
  headline: z.string().nullable(),
  /** Lo más importante del día, en bullets. Vacío si todavía está `pending`. */
  highlights: z.array(z.string()),
});
export type Recap = z.infer<typeof RecapSchema>;
