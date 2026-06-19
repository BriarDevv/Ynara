import { AdminUsersOut, type AdminUsersOutT } from "@/features/users/schemas";
import type { RangeId } from "@/stores/range";
import { FIXTURE_NOW, heatLevel, mulberry32, weeklySeasonalSeries } from "./seed";

/**
 * Fixture de `GET /v1/admin/users` (blueprint §4.7).
 *
 * DAU≈180 / WAU≈620 / MAU≈1100 (proxy por sesiones), heatmap 53×7 con
 * estacionalidad semanal, conversion ephemeral 740 / registered 500 (≈40%),
 * signups crecientes. Los flags `isApproximate`/`isEstimate` van en `true` (la
 * UI los rotula; el schema los exige literales).
 *
 * El `range` solo desplaza la seed de los sparklines (la actividad puntual y el
 * heatmap son una foto estable de las últimas 53 semanas, no dependen del rango
 * elegido en el topbar).
 */

const RANGE_SEED: Record<RangeId, number> = {
  "24h": 211,
  "7d": 217,
  "30d": 230,
  "90d": 290,
};

/** Heatmap 53×7 (~371 días) con estacionalidad semanal y nivel por cuantiles. */
function buildHeatmap(seed: number, now: Date = FIXTURE_NOW): AdminUsersOutT["heatmap"] {
  const series = weeklySeasonalSeries(53 * 7, 16, seed + 7, now);
  return series.map(({ date, value }) => ({
    date,
    count: value,
    level: heatLevel(value),
  }));
}

export function usersFixture(range: RangeId, now: Date = FIXTURE_NOW): AdminUsersOutT {
  const seed = RANGE_SEED[range];
  const rand = mulberry32(seed);
  const spark = (offset: number) =>
    weeklySeasonalSeries(14, 30, seed + offset, now).map((p) => p.value);

  const data: AdminUsersOutT = {
    activity: {
      dau: { value: 180, delta: { pct: 2.6, direction: "up" }, spark: spark(1) },
      wau: { value: 620, delta: { pct: 1.4, direction: "up" }, spark: spark(2) },
      mau: { value: 1100, delta: { pct: 0.8, direction: "flat" }, spark: spark(3) },
      is_approximate: true,
    },
    heatmap: buildHeatmap(seed, now),
    conversion: {
      ephemeral: 740,
      registered: 500,
      conversion_pct: 40.3,
      is_estimate: true,
    },
    signups: weeklySeasonalSeries(30, 14, seed + 4, now).map(({ date }, i) => ({
      date,
      // tendencia creciente + jitter determinista
      count: 8 + Math.round((i / 29) * 18) + Math.floor(rand() * 4),
    })),
  };

  return AdminUsersOut.parse(data);
}
