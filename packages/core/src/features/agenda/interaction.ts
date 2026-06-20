/**
 * **Matemática pura de interacción** del time-grid (drag-crear / mover / resize),
 * compartida por web (pointer events) y mobile (gesture-handler + Reanimated).
 * Son funciones puras y worklet-safe: convierten px↔minutos, snappean a un
 * incremento y clampean al día. El *binding* de gestos vive en cada plataforma;
 * acá está solo el cálculo (CALENDAR-RESEARCH-2026 §5.B).
 */

/** Incremento de snap por defecto (minutos). */
export const SNAP_MIN = 15;
/** Minutos en un día. */
export const DAY_MIN = 1440;

/** px → minutos, dado `rowPx` (px por hora de la grilla). */
export function pxToMinutes(px: number, rowPx: number): number {
  return (px / rowPx) * 60;
}

/** minutos → px, dado `rowPx`. */
export function minutesToPx(minutes: number, rowPx: number): number {
  return (minutes / 60) * rowPx;
}

/** Redondea `minutes` al múltiplo de `step` más cercano. */
export function snapMinutes(minutes: number, step = SNAP_MIN): number {
  return Math.round(minutes / step) * step;
}

/**
 * Nuevo inicio (minutos del día) al **mover** un bloque por un delta vertical
 * `deltaPx`: snappeado a `step` y clampeado a `[0, dayMin - durationMin]` para
 * que el bloque no se salga del día.
 */
export function dragStart(
  originalStartMin: number,
  deltaPx: number,
  rowPx: number,
  durationMin: number,
  step = SNAP_MIN,
  dayMin = DAY_MIN,
): number {
  const moved = snapMinutes(originalStartMin + pxToMinutes(deltaPx, rowPx), step);
  return Math.max(0, Math.min(moved, dayMin - durationMin));
}

/**
 * Nueva duración (minutos) al **redimensionar** desde el borde inferior por
 * `deltaPx`: snappeada a `step`, mínimo `step`, máximo hasta el fin del día.
 */
export function resizeDuration(
  originalDurationMin: number,
  deltaPx: number,
  rowPx: number,
  startMin: number,
  step = SNAP_MIN,
  dayMin = DAY_MIN,
): number {
  const dur = snapMinutes(originalDurationMin + pxToMinutes(deltaPx, rowPx), step);
  return Math.max(step, Math.min(dur, dayMin - startMin));
}

/**
 * Inicio (minutos del día) al **crear** arrastrando desde una posición `yPx`
 * medida desde el tope de la grilla. `minH` = primera hora visible. Snappeado.
 */
export function createStart(yPx: number, minH: number, rowPx: number, step = SNAP_MIN): number {
  const min = minH * 60 + pxToMinutes(yPx, rowPx);
  return Math.max(0, Math.min(snapMinutes(min, step), DAY_MIN - step));
}
