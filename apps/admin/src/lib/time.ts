import type { RangeId } from "@/stores/range";

/**
 * Helpers de tiempo del panel: rangos temporales globales (24h/7d/30d/90d),
 * cálculo de ventanas [from, to) y formateo numérico con `tabular-nums`
 * (regla dura del DS: todo número del panel usa cifras tabulares).
 *
 * Puro y testeable: `now` es inyectable para no mockear el reloj.
 */

/** Etiqueta corta del rango para los segmented controls. */
export const RANGE_LABEL: Record<RangeId, string> = {
  "24h": "24h",
  "7d": "7d",
  "30d": "30d",
  "90d": "90d",
};

/** Etiqueta humana del rango (captions, tooltips). */
export const RANGE_HUMAN: Record<RangeId, string> = {
  "24h": "Últimas 24 horas",
  "7d": "Últimos 7 días",
  "30d": "Últimos 30 días",
  "90d": "Últimos 90 días",
};

/** Duración del rango en milisegundos. */
export const RANGE_MS: Record<RangeId, number> = {
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
  "90d": 90 * 24 * 60 * 60 * 1000,
};

/** Cantidad de días que abarca el rango (1 para 24h). */
export const RANGE_DAYS: Record<RangeId, number> = {
  "24h": 1,
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

export type TimeWindow = { from: Date; to: Date };

/**
 * Ventana [from, to) del rango terminando en `now`. La ventana anterior (para
 * deltas) es [from - dur, from).
 */
export function rangeWindow(range: RangeId, now: Date = new Date()): TimeWindow {
  const to = now;
  const from = new Date(to.getTime() - RANGE_MS[range]);
  return { from, to };
}

/** Ventana del período inmediatamente anterior, para comparar deltas. */
export function previousWindow(range: RangeId, now: Date = new Date()): TimeWindow {
  const { from } = rangeWindow(range, now);
  return { from: new Date(from.getTime() - RANGE_MS[range]), to: from };
}

// ---- Formateo numérico (siempre pensado para render con `tabular-nums`) ----

const intFmt = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });
const pctFmt = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** Entero con separador de miles (es-AR). */
export function fmtInt(value: number): string {
  return intFmt.format(value);
}

/** Porcentaje con 1 decimal y signo `%`. Recibe el valor ya en porcentaje. */
export function fmtPct(value: number): string {
  return `${pctFmt.format(value)}%`;
}

/** Milisegundos legibles (`3.2 ms`). */
export function fmtMs(value: number): string {
  return `${pctFmt.format(value)} ms`;
}

/** Minutos legibles (`12 min`). */
export function fmtMin(value: number): string {
  return `${Math.round(value)} min`;
}

/** Delta con signo y 1 decimal (`+4.2%` / `-1.0%` / `0%`). */
export function fmtDelta(pct: number): string {
  if (pct === 0) return "0%";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pctFmt.format(pct)}%`;
}

/** Dispatcher de formato por tipo de métrica del panel. */
export function fmtValue(value: number, format: "int" | "pct" | "ms" | "min" = "int"): string {
  switch (format) {
    case "pct":
      return fmtPct(value);
    case "ms":
      return fmtMs(value);
    case "min":
      return fmtMin(value);
    default:
      return fmtInt(value);
  }
}
