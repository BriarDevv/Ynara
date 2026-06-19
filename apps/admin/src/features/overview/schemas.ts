import { z } from "zod";
import { Delta, ModeId, TimePoint } from "@/features/_shared/schemas";

/**
 * Contrato de `GET /v1/admin/overview?range=` (blueprint §4.1).
 *
 * Pantalla F1.1: estado del perímetro + 4 KPIs + serie de sesiones/día + mix de
 * modos compacto + preview de 6 filas de audit. Todos los conteos son enteros;
 * las fechas ISO 8601 UTC.
 *
 * `auditPreview` ya respeta la regla de privacidad del audit log: trae solo los
 * campos exponibles (sin `record_hash`, sin `target_id`, sin contenido).
 */

/** Perímetro de soberanía que pinta el `PerimeterBadge` del hero. */
export const OverviewPerimeter = z.object({
  status: z.enum(["intact", "attention", "verifying"]),
  detail: z.string().nullable(),
  checked_at: z.string(),
});
export type OverviewPerimeterT = z.infer<typeof OverviewPerimeter>;

/** KPI sin sparkline (valor + delta contra período anterior). */
const KpiBare = z.object({
  value: z.number().int(),
  delta: Delta,
});

/** KPI con sparkline (serie corta para el mini-gráfico de la card). */
const KpiWithSpark = KpiBare.extend({
  spark: z.array(z.number()),
});

export const AdminOverviewOut = z.object({
  perimeter: OverviewPerimeter,
  kpis: z.object({
    users_total: KpiBare,
    sessions: KpiWithSpark,
    memories: KpiBare, // suma de las 3 capas del moat
    audit_events: KpiBare,
  }),
  sessions_series: z.array(TimePoint),
  mode_mix: z.array(z.object({ mode: ModeId, value: z.number().int() })),
  audit_preview: z.array(
    z.object({
      id: z.string().uuid(),
      created_at: z.string(),
      operation: z.enum(["read", "write", "update", "delete"]),
      target_layer: z.enum(["semantic", "episodic", "procedural"]),
      origin_mode: ModeId.nullable(),
      sensitive: z.boolean(),
    }),
  ),
});

export type AdminOverviewOutT = z.infer<typeof AdminOverviewOut>;
