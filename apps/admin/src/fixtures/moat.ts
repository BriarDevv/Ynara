import { AdminMoatOut, type AdminMoatOutT, type MoatLayerT } from "@/features/moat/schemas";
import { RANGE_DAYS } from "@/lib/time";
import type { RangeId } from "@/stores/range";
import { daysBack, FIXTURE_NOW, minutesBack, mulberry32, seededUuid } from "./seed";

/**
 * Fixture de `GET /v1/admin/moat` (blueprint §4.7).
 *
 * counts {semantic 8400, episodic 2100, procedural 460}, 3 series de crecimiento
 * ascendentes, procedural staleCount 38 / healthy 422, buckets de confidence,
 * backlog 12 + recentEpisodic (solo metadata, sin contenido).
 *
 * Privacidad: `recentEpisodic` jamás trae `summary`/`content` — id + timestamp +
 * flag de sensible y nada más.
 */

const RANGE_SEED: Record<RangeId, number> = {
  "24h": 401,
  "7d": 407,
  "30d": 430,
  "90d": 490,
};

const COUNTS = { semantic: 8400, episodic: 2100, procedural: 460 } as const;

/** Serie de crecimiento acumulado por capa: termina en su count actual. */
function growthSeries(
  key: MoatLayerT,
  endCount: number,
  days: number,
  seed: number,
  now: Date,
): { key: MoatLayerT; points: { date: string; value: number }[] } {
  const dates = daysBack(days, now);
  const rand = mulberry32(seed);
  const start = Math.round(endCount * 0.82); // empezó 18% más bajo
  const points = dates.map((date, i) => {
    const progress = i / Math.max(1, days - 1);
    const jitter = 1 + (rand() - 0.5) * 0.02;
    return { date, value: Math.round((start + (endCount - start) * progress) * jitter) };
  });
  return { key, points };
}

export function moatFixture(range: RangeId, now: Date = FIXTURE_NOW): AdminMoatOutT {
  const seed = RANGE_SEED[range];
  const days = RANGE_DAYS[range];

  const data: AdminMoatOutT = {
    counts: { ...COUNTS },
    deltas: {
      semantic: { pct: 4.1, direction: "up" },
      episodic: { pct: 2.8, direction: "up" },
      procedural: { pct: 0.4, direction: "flat" },
    },
    growth: [
      growthSeries("semantic", COUNTS.semantic, days, seed + 1, now),
      growthSeries("episodic", COUNTS.episodic, days, seed + 2, now),
      growthSeries("procedural", COUNTS.procedural, days, seed + 3, now),
    ],
    procedural: {
      stale_count: 38,
      healthy_count: 422,
      confidence_buckets: [
        { range: "0.0–0.2", count: 6 },
        { range: "0.2–0.4", count: 14 },
        { range: "0.4–0.6", count: 58 },
        { range: "0.6–0.8", count: 162 },
        { range: "0.8–1.0", count: 220 },
      ],
    },
    consolidation: {
      backlog: 12,
      recent_episodic: Array.from({ length: 8 }, (_, i) => ({
        id: seededUuid(seed * 31 + i),
        occurred_at: minutesBack(i * 13 + 4, now),
        is_sensitive: mulberry32(seed + i)() < 0.22,
      })),
    },
  };

  return AdminMoatOut.parse(data);
}
