import { z } from "zod";
import { Delta, HeatLevel } from "@/features/_shared/schemas";

/**
 * Contrato de `GET /v1/admin/users?range=` (blueprint §4.2).
 *
 * Pantalla F1.2: actividad (DAU/WAU/MAU) + heatmap 53×7 + funnel de conversión +
 * signups/día.
 *
 * Honestidad de dato (regla #6): no existe `last_seen`, así que DAU/WAU/MAU son
 * un **proxy por sesiones** y la conversión un **estimado** (no hay timestamp de
 * conversión). El schema clava esos flags como `z.literal(true)` para que la UI
 * NO pueda olvidar rotularlos: si el backend manda `false`, el parse falla.
 */

/** Métrica de actividad con sparkline (siempre approximate, ver `is_approximate`). */
const ActivityMetric = z.object({
  value: z.number().int(),
  delta: Delta,
  spark: z.array(z.number()),
});

export const AdminUsersOut = z.object({
  activity: z.object({
    dau: ActivityMetric,
    wau: ActivityMetric,
    mau: ActivityMetric,
    is_approximate: z.literal(true), // proxy por sesiones (gap #1)
  }),
  heatmap: z.array(
    z.object({
      date: z.string(),
      count: z.number().int().nonnegative(),
      level: HeatLevel,
    }),
  ),
  conversion: z.object({
    ephemeral: z.number().int(),
    registered: z.number().int(),
    conversion_pct: z.number(),
    is_estimate: z.literal(true),
  }),
  signups: z.array(z.object({ date: z.string(), count: z.number().int() })),
});

export type AdminUsersOutT = z.infer<typeof AdminUsersOut>;
