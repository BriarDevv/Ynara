import { z } from "zod";

/**
 * Tipos base compartidos por los contratos `/v1/admin/*` (blueprint §4.0).
 *
 * Viven acá (en `features/_shared`) y no en `lib/` porque son parte del
 * **contrato de API del panel**, no infra: cada `features/<f>/schemas.ts` los
 * compone para describir su endpoint. Mantenerlos juntos evita drift entre las
 * 6 vistas (un solo `ModeId`, un solo `Delta`, un solo `TimePoint`).
 *
 * Regla de privacidad transversal: ningún schema de admin expone contenido
 * descifrado de memoria, `record_hash` ni `target_id`. Eso se materializa en
 * cada feature (audit omite esos campos del schema, no solo del render).
 */

/** Los 5 modos de Ynara (espeja `@/components/ui/modes`). */
export const ModeId = z.enum(["productividad", "estudio", "bienestar", "vida", "memoria"]);
export type ModeIdT = z.infer<typeof ModeId>;

/** Ventana temporal global del panel (segmented control del topbar). */
export const RangeId = z.enum(["24h", "7d", "30d", "90d"]);
export type RangeIdT = z.infer<typeof RangeId>;

/**
 * Variación contra el período anterior. `pct` es el cambio porcentual (puede ser
 * negativo); `direction` es la flecha que pinta la UI (▲/▼/neutro). Se separan
 * para que el render no tenga que re-derivar el signo del número.
 */
export const Delta = z.object({
  pct: z.number(),
  direction: z.enum(["up", "down", "flat"]),
});
export type DeltaT = z.infer<typeof Delta>;

/**
 * Punto de una serie temporal: `date` ISO 8601 (UTC) + `value` entero no
 * negativo (conteo del día). Lo usan las series de sesiones y de crecimiento
 * del moat.
 */
export const TimePoint = z.object({
  date: z.string(),
  value: z.number().int().nonnegative(),
});
export type TimePointT = z.infer<typeof TimePoint>;

/**
 * Nivel de intensidad discreto del heatmap de actividad (escala plana de azul
 * `--heat-0..5`). Union literal `0..5` (no `number`) para que el fixture, el
 * contrato Zod y el componente (`UsageHeatmap`) compartan EXACTAMENTE el mismo
 * tipo sin casts. Es estrictamente equivalente a un entero `[0, 5]` pero el tipo
 * inferido es el union, no `number`.
 */
export const HeatLevel = z.union([
  z.literal(0),
  z.literal(1),
  z.literal(2),
  z.literal(3),
  z.literal(4),
  z.literal(5),
]);
export type HeatLevel = z.infer<typeof HeatLevel>;
