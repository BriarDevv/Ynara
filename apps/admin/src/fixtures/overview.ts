import { AdminOverviewOut, type AdminOverviewOutT } from "@/features/overview/schemas";
import { RANGE_DAYS } from "@/lib/time";
import type { RangeId } from "@/stores/range";
import {
  FIXTURE_NOW,
  minutesBack,
  mulberry32,
  pick,
  seededUuid,
  weeklySeasonalSeries,
} from "./seed";

/**
 * Fixture de `GET /v1/admin/overview` (blueprint §4.7).
 *
 * Determinista por `range`: cada rango deriva su propia seed, así 7d y 30d dan
 * datos distintos pero estables. Valores realistas — ~1240 users, sesiones con
 * picos lun–vie, mix con productividad dominante, 6 filas de audit preview.
 *
 * Se devuelve YA PARSEADO por `AdminOverviewOut`: el fixture es la garantía viva
 * de que el contrato Zod y los datos de demo no driftean.
 */

/** Seed base por rango (suma un offset por rango para variar entre ventanas). */
const RANGE_SEED: Record<RangeId, number> = {
  "24h": 101,
  "7d": 107,
  "30d": 130,
  "90d": 190,
};

const OPERATIONS = ["read", "write", "update", "delete"] as const;
const LAYERS = ["semantic", "episodic", "procedural"] as const;
const MODES = ["productividad", "estudio", "bienestar", "vida", "memoria"] as const;

/** Construye el preview de 6 filas de audit (solo campos exponibles). */
function buildAuditPreview(seed: number): AdminOverviewOutT["audit_preview"] {
  const rand = mulberry32(seed);
  return Array.from({ length: 6 }, (_, i) => ({
    id: seededUuid(seed + i),
    created_at: minutesBack(i * 7 + 2),
    operation: pick(OPERATIONS, Math.floor(rand() * OPERATIONS.length)),
    target_layer: pick(LAYERS, Math.floor(rand() * LAYERS.length)),
    origin_mode: rand() < 0.2 ? null : pick(MODES, Math.floor(rand() * MODES.length)),
    sensitive: rand() < 0.18,
  }));
}

export function overviewFixture(range: RangeId, now: Date = FIXTURE_NOW): AdminOverviewOutT {
  const seed = RANGE_SEED[range];
  const days = RANGE_DAYS[range];
  const sessions_series = weeklySeasonalSeries(days, 210, seed, now);
  const sessionsTotal = sessions_series.reduce((acc, p) => acc + p.value, 0);
  const spark = sessions_series.slice(-14).map((p) => p.value);

  const data: AdminOverviewOutT = {
    perimeter: {
      status: "intact",
      detail: "Token no viaja a host ajeno · contenido cifrado · hash no expuesto",
      checked_at: minutesBack(1, now),
    },
    kpis: {
      users_total: { value: 1240, delta: { pct: 3.4, direction: "up" } },
      sessions: { value: sessionsTotal, delta: { pct: 5.1, direction: "up" }, spark },
      memories: { value: 8400 + 2100 + 460, delta: { pct: 2.2, direction: "up" } }, // suma 3 capas
      audit_events: {
        value: Math.round(sessionsTotal * 1.8),
        delta: { pct: -1.2, direction: "down" },
      },
    },
    sessions_series,
    mode_mix: [
      { mode: "productividad", value: Math.round(sessionsTotal * 0.42) },
      { mode: "estudio", value: Math.round(sessionsTotal * 0.23) },
      { mode: "bienestar", value: Math.round(sessionsTotal * 0.14) },
      { mode: "vida", value: Math.round(sessionsTotal * 0.12) },
      { mode: "memoria", value: Math.round(sessionsTotal * 0.09) },
    ],
    audit_preview: buildAuditPreview(seed),
  };

  return AdminOverviewOut.parse(data);
}
