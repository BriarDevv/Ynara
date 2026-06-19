/**
 * Utilidades geométricas compartidas por los charts del panel — escalas,
 * ticks, builders de `path` SVG y mapeos de layout. **Puro y sin color**: acá
 * no se referencia ningún token ni hex (el color lo deciden los componentes con
 * `var(--...)`); esto solo hace números → coordenadas. Mantenerlo color-free es
 * lo que deja pasar el gradient-guard y simplifica el testeo.
 *
 * Convención de todos los charts: `viewBox` en coordenadas de usuario, eje Y
 * invertido (SVG crece hacia abajo, así que `value` alto → `y` chico). Las
 * series temporales se normalizan a un `viewBox` fijo y se estiran con
 * `preserveAspectRatio` cuando hace falta que el ancho sea fluido.
 */

// tabular-nums-guard: n/a — solo geometría/escalas, no renderiza dígitos en pantalla.

/** Punto de una serie temporal (fecha ISO + valor). */
export type SeriesPoint = { date: string; value: number };

/** Coordenada cartesiana ya proyectada al `viewBox`. */
export type XY = { x: number; y: number };

/** Caja de dibujo: dimensiones del `viewBox` + padding interno para ejes. */
export type ChartBox = {
  width: number;
  height: number;
  padding: { top: number; right: number; bottom: number; left: number };
};

/** Box default cómodo para series temporales con ejes (left/bottom). */
export const DEFAULT_BOX: ChartBox = {
  width: 720,
  height: 240,
  padding: { top: 12, right: 12, bottom: 28, left: 40 },
};

/** Ancho útil del área de plot (descontando padding). */
export function plotWidth(box: ChartBox): number {
  return box.width - box.padding.left - box.padding.right;
}

/** Alto útil del área de plot (descontando padding). */
export function plotHeight(box: ChartBox): number {
  return box.height - box.padding.top - box.padding.bottom;
}

/** Mínimo y máximo de una lista (con fallback a 0 si está vacía). */
export function extent(values: number[]): { min: number; max: number } {
  if (values.length === 0) return { min: 0, max: 0 };
  // Ya descartamos el caso vacío, así que `Math.min/max` devuelven `number`
  // (sobre `[]` darían ±Infinity, de ahí el guard previo).
  return { min: Math.min(...values), max: Math.max(...values) };
}

/**
 * Escala lineal genérica `domain → range`. Si el dominio es degenerado
 * (min === max) devuelve el centro del range para no dividir por cero.
 */
export function scaleLinear(
  domainMin: number,
  domainMax: number,
  rangeMin: number,
  rangeMax: number,
): (value: number) => number {
  const span = domainMax - domainMin;
  if (span === 0) {
    const mid = (rangeMin + rangeMax) / 2;
    return () => mid;
  }
  return (value: number) => rangeMin + ((value - domainMin) / span) * (rangeMax - rangeMin);
}

/**
 * Genera hasta `count` ticks "lindos" (pasos 1/2/5·10ⁿ) cubriendo [min, max].
 * Útil para el eje Y; devuelve valores del dominio (sin proyectar).
 */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const span = max - min;
  const rawStep = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const norm = rawStep / mag;
  const niceStep = (norm >= 5 ? 5 : norm >= 2 ? 2 : 1) * mag;
  const start = Math.ceil(min / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let t = start; t <= max + niceStep * 1e-9; t += niceStep) {
    // Redondeo defensivo contra el drift de coma flotante en la acumulación.
    ticks.push(Math.round(t / niceStep) * niceStep);
  }
  return ticks;
}

/**
 * Proyecta una serie temporal al área de plot de `box`. El eje X reparte los
 * puntos uniformemente (índice → ancho); el eje Y usa [0, max] por default para
 * que el baseline sea 0 (lo correcto para conteos), salvo que se pase `yMin`.
 */
export function projectSeries(
  points: SeriesPoint[],
  box: ChartBox,
  opts: { yMin?: number; yMax?: number } = {},
): XY[] {
  if (points.length === 0) return [];
  const { padding } = box;
  const w = plotWidth(box);
  const h = plotHeight(box);
  const values = points.map((p) => p.value);
  const { max } = extent(values);
  const yMin = opts.yMin ?? 0;
  const yMax = opts.yMax ?? (max === 0 ? 1 : max);
  const xScale = scaleLinear(0, Math.max(1, points.length - 1), padding.left, padding.left + w);
  const yScale = scaleLinear(yMin, yMax, padding.top + h, padding.top);
  return points.map((p, i) => ({ x: xScale(i), y: yScale(p.value) }));
}

/** `d` de una polilínea (línea recta entre puntos) a partir de coordenadas. */
export function linePath(coords: XY[]): string {
  if (coords.length === 0) return "";
  return coords
    .map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(2)} ${c.y.toFixed(2)}`)
    .join(" ");
}

/**
 * `d` de un área cerrada bajo una línea (para el relleno plano de
 * `AreaTimeSeries`): la polilínea + bajada al baseline + cierre.
 */
export function areaPath(coords: XY[], baselineY: number): string {
  const first = coords[0];
  const last = coords.at(-1);
  // Guarda real sobre ambos extremos (cubre el caso vacío y satisface el tipo).
  if (first === undefined || last === undefined) return "";
  const top = linePath(coords);
  return `${top} L${last.x.toFixed(2)} ${baselineY.toFixed(2)} L${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`;
}

/**
 * Path de un sparkline normalizado a un `viewBox` 0..w × 0..h. Pensado para
 * usarse con `preserveAspectRatio="none"` (se estira al contenedor). Sin ejes.
 */
export function sparklinePath(data: number[], width: number, height: number): string {
  if (data.length === 0) return "";
  const { min, max } = extent(data);
  const xScale = scaleLinear(0, Math.max(1, data.length - 1), 0, width);
  // 1px de respiro arriba/abajo para que la línea no se corte contra el borde.
  const yScale = scaleLinear(min, max, height - 1, 1);
  const coords = data.map((v, i) => ({ x: xScale(i), y: yScale(v) }));
  return linePath(coords);
}

/** Describe un arco de donut (slice) como `path` SVG entre dos ángulos. */
export type ArcSpec = {
  cx: number;
  cy: number;
  innerR: number;
  outerR: number;
  startAngle: number; // radianes, 0 = arriba (12 en punto), horario
  endAngle: number;
};

function polar(cx: number, cy: number, r: number, angle: number): XY {
  // angle 0 → arriba; sentido horario.
  return { x: cx + r * Math.sin(angle), y: cy - r * Math.cos(angle) };
}

/** `d` de un slice de donut (anillo) entre `startAngle` y `endAngle`. */
export function donutSlicePath(spec: ArcSpec): string {
  const { cx, cy, innerR, outerR, startAngle, endAngle } = spec;
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  const oStart = polar(cx, cy, outerR, startAngle);
  const oEnd = polar(cx, cy, outerR, endAngle);
  const iEnd = polar(cx, cy, innerR, endAngle);
  const iStart = polar(cx, cy, innerR, startAngle);
  return [
    `M${oStart.x.toFixed(2)} ${oStart.y.toFixed(2)}`,
    `A${outerR} ${outerR} 0 ${largeArc} 1 ${oEnd.x.toFixed(2)} ${oEnd.y.toFixed(2)}`,
    `L${iEnd.x.toFixed(2)} ${iEnd.y.toFixed(2)}`,
    `A${innerR} ${innerR} 0 ${largeArc} 0 ${iStart.x.toFixed(2)} ${iStart.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

/**
 * Reparte valores en slices angulares contiguos (donut). Devuelve, por entrada,
 * el ángulo inicial/final en radianes y la fracción del total.
 */
export function sliceAngles<T extends { value: number }>(
  items: T[],
): Array<T & { startAngle: number; endAngle: number; fraction: number }> {
  const total = items.reduce((sum, it) => sum + it.value, 0);
  let cursor = 0;
  return items.map((it) => {
    const fraction = total === 0 ? 0 : it.value / total;
    const startAngle = cursor * 2 * Math.PI;
    cursor += fraction;
    const endAngle = cursor * 2 * Math.PI;
    return { ...it, startAngle, endAngle, fraction };
  });
}

/** Día de la semana (0 = domingo) de una fecha ISO `YYYY-MM-DD`, UTC. */
export function isoWeekday(date: string): number {
  return new Date(`${date}T00:00:00Z`).getUTCDay();
}

/**
 * Layout de heatmap estilo "contribuciones": agrupa celdas en columnas
 * semanales. Cada celda recibe `col` (semana, 0..n) y `row` (día, 0..6). Asume
 * que `cells` viene ordenado cronológicamente ascendente.
 */
export function heatmapLayout<T extends { date: string }>(
  cells: T[],
): Array<T & { col: number; row: number }> {
  const head = cells[0];
  if (head === undefined) return [];
  const firstWeekday = isoWeekday(head.date);
  return cells.map((cell, i) => {
    const offset = i + firstWeekday;
    return { ...cell, col: Math.floor(offset / 7), row: offset % 7 };
  });
}
