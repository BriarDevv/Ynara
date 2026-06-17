import { z } from "zod";

import { ModeSchema } from "./modes";

/**
 * Contrato del dominio **Agenda** (build-plan Fase F): el día/semana de bloques
 * horarios (wireframes 10/11).
 *
 * **PROVISIONAL — todavía no hay backend.** No existe el modelo `CalendarEvent`
 * ni `/v1/events`; el dominio se construye *mock-first* (como Hoy): estos schemas
 * son el contrato tipado contra el que corre el handler mock, y la fuente de
 * verdad cuando el backend exista. Track backend (FRONTEND-APP-BUILD-PLAN §4):
 * `CalendarEvent` model + CRUD `/v1/events` *(gate regla #1 + decisión modelo
 * propio, ya tomada)*.
 *
 * Snake_case y `datetime({ offset: true })` para espejar la convención Pydantic
 * del backend ("Pydantic gana, Zod sigue"): al cablear el endpoint real el shape
 * ya coincide. El **fin** del bloque es derivado (`start_at + duration_min`), no
 * un campo aparte: una sola fuente de verdad (igual que `Task`).
 *
 * El tipo se llama `AgendaEvent` (no `Event`) para no chocar con el `Event` del
 * DOM en TS.
 */

/** Estado de un evento. `tentative` = sin confirmar; `cancelled` = se muestra tachado. */
export const EventStatusSchema = z.enum(["confirmed", "tentative", "cancelled"]);
export type EventStatus = z.infer<typeof EventStatusSchema>;

/**
 * Un evento de la agenda. `start_at` + `duration_min` arman el bloque ("14:00 ·
 * 45 min"); el fin se deriva. `mode` lo tinta y lo asocia a un modo (`null` si es
 * transversal). `location` es la nota/lugar opcional (subtítulo del bloque).
 */
export const AgendaEventSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  /** Inicio del bloque (ISO con offset). */
  start_at: z.string().datetime({ offset: true }),
  /** Duración en minutos (> 0). El fin es `start_at + duration_min` (derivado). */
  duration_min: z.number().int().positive(),
  /** Modo al que pertenece (para el tint), o `null` si es transversal. */
  mode: ModeSchema.nullable(),
  /** Estado del evento. */
  status: EventStatusSchema,
  /** Nota o lugar opcional (subtítulo del bloque). `null` si no tiene. */
  location: z.string().nullable(),
});
export type AgendaEvent = z.infer<typeof AgendaEventSchema>;

/** Respuesta de `GET /v1/events`: los eventos (del día/rango pedido) + el total. */
export const EventsResponseSchema = z.object({
  items: z.array(AgendaEventSchema),
  total: z.number().int().nonnegative(),
});
export type EventsResponse = z.infer<typeof EventsResponseSchema>;

/**
 * Body de `POST /v1/events` (crear). Form mínimo: título + inicio + duración; el
 * `mode` y la `location` son opcionales (el server/mock completa `null` por
 * default), y el `status` arranca `confirmed`.
 */
export const EventCreateSchema = z.object({
  title: z.string().min(1),
  start_at: z.string().datetime({ offset: true }),
  duration_min: z.number().int().positive(),
  mode: ModeSchema.nullable().optional(),
  location: z.string().nullable().optional(),
});
export type EventCreate = z.infer<typeof EventCreateSchema>;

/**
 * Body de `PATCH /v1/events/{id}` (editar). Update parcial: cualquier campo
 * editable puede mandarse; los no enviados quedan intactos.
 */
export const EventPatchSchema = z.object({
  title: z.string().min(1).optional(),
  start_at: z.string().datetime({ offset: true }).optional(),
  duration_min: z.number().int().positive().optional(),
  mode: ModeSchema.nullable().optional(),
  status: EventStatusSchema.optional(),
  location: z.string().nullable().optional(),
});
export type EventPatch = z.infer<typeof EventPatchSchema>;
