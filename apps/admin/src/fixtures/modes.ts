import type { ModeIdT } from "@/features/_shared/schemas";
import { AdminModesOut, type AdminModesOutT } from "@/features/modes/schemas";
import { RANGE_DAYS } from "@/lib/time";
import type { RangeId } from "@/stores/range";

/**
 * Fixture de `GET /v1/admin/modes` (blueprint §4.7).
 *
 * Mix [productividad 42%, estudio 23%, bienestar 14%, vida 12%, memoria 9%].
 * Duración media por modo (memoria la más larga: sesiones de recordar son más
 * extensas), con `closedSessions`/`openSessions` coherentes para poder rotular
 * "media de N cerradas". El total escala con los días del rango.
 */

/** Pesos del mix por modo (suman 1.0). Orden de dominancia del producto. */
const MIX_WEIGHTS: { mode: ModeIdT; pct: number; avg_minutes: number }[] = [
  { mode: "productividad", pct: 42, avg_minutes: 9.4 },
  { mode: "estudio", pct: 23, avg_minutes: 18.7 },
  { mode: "bienestar", pct: 14, avg_minutes: 12.1 },
  { mode: "vida", pct: 12, avg_minutes: 7.8 },
  { mode: "memoria", pct: 9, avg_minutes: 21.5 },
];

export function modesFixture(range: RangeId): AdminModesOutT {
  // ~210 sesiones/día base × días del rango → total coherente con overview.
  const total = Math.round(210 * RANGE_DAYS[range] * 0.98);

  const mix = MIX_WEIGHTS.map(({ mode, pct }) => ({
    mode,
    sessions: Math.round((total * pct) / 100),
    pct,
  }));

  const duration = MIX_WEIGHTS.map(({ mode, pct, avg_minutes }) => {
    const sessions = Math.round((total * pct) / 100);
    const open = Math.round(sessions * 0.07); // ~7% en curso
    return {
      mode,
      avg_minutes,
      closed_sessions: sessions - open,
      open_sessions: open,
    };
  });

  return AdminModesOut.parse({ total, mix, duration });
}
