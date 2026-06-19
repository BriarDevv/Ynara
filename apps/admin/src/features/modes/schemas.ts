import { z } from "zod";
import { ModeId } from "@/features/_shared/schemas";

/**
 * Contrato de `GET /v1/admin/modes?range=` (blueprint §4.3).
 *
 * Pantalla F1.3: mix de modos (donut count/%) + duración media por modo.
 *
 * Honestidad de dato (regla #6): la duración media solo se calcula sobre
 * sesiones **cerradas** (`ended_at IS NOT NULL`). Se exponen `closedSessions` y
 * `openSessions` por modo para que la UI pueda rotular "media de N cerradas (M
 * abiertas)" y nunca insinuar que el promedio cubre sesiones en curso.
 */

export const AdminModesOut = z.object({
  total: z.number().int(),
  mix: z.array(
    z.object({
      mode: ModeId,
      sessions: z.number().int(),
      pct: z.number(),
    }),
  ),
  duration: z.array(
    z.object({
      mode: ModeId,
      avg_minutes: z.number(),
      closed_sessions: z.number().int(),
      open_sessions: z.number().int(),
    }),
  ),
});

export type AdminModesOutT = z.infer<typeof AdminModesOut>;
