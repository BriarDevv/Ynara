import type { LayoutInterval } from "@ynara/core/features/agenda";
import type { AgendaEvent } from "./api";

/**
 * Helpers puros de presentación de la Agenda (hora, rango, semana). Operan en
 * **hora local** (el bloque se muestra en el huso del usuario); el `start_at`
 * viaja en ISO con offset y se re-localiza acá.
 */

const MS_PER_MIN = 60_000;

function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Hora local "HH:MM" de un ISO. */
export function formatTime(iso: string): string {
  return hhmm(new Date(iso));
}

/** Fin del bloque = inicio + duración (derivado, una sola fuente de verdad). */
export function eventEnd(event: AgendaEvent): Date {
  return new Date(new Date(event.start_at).getTime() + event.duration_min * MS_PER_MIN);
}

/** Rango horario legible del bloque: `"10:00 – 11:30"`. */
export function formatEventRange(event: AgendaEvent): string {
  return `${hhmm(new Date(event.start_at))} – ${hhmm(eventEnd(event))}`;
}

/** Lunes 00:00 (local) de la semana que contiene `date` (semana ISO, lun→dom). */
export function startOfWeek(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const dow = (d.getDay() + 6) % 7; // 0 = lunes … 6 = domingo
  d.setDate(d.getDate() - dow);
  return d;
}

/** Los 7 días (lunes→domingo, 00:00 local) de la semana de `date`. */
export function weekDays(date: Date): Date[] {
  const monday = startOfWeek(date);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(d.getDate() + i);
    return d;
  });
}

/** Primer día (00:00 local) del mes que contiene `date`. */
export function startOfMonth(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(1);
  return d;
}

/**
 * Los 42 días (6 semanas lunes→domingo) de la grilla del mes que contiene
 * `date`: arranca en el lunes de la semana del día 1 y cubre **6 filas fijas**
 * (evita layout-shift al cambiar de mes). Incluye días del mes anterior/siguiente
 * para completar las semanas.
 */
export function monthGridDays(date: Date): Date[] {
  const first = startOfWeek(startOfMonth(date));
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(first);
    d.setDate(d.getDate() + i);
    return d;
  });
}

/** ¿El evento ocurre el día local `day`? (compara año/mes/día local). */
export function isOnDay(event: AgendaEvent, day: Date): boolean {
  const start = new Date(event.start_at);
  return (
    start.getFullYear() === day.getFullYear() &&
    start.getMonth() === day.getMonth() &&
    start.getDate() === day.getDate()
  );
}

/** Eventos del día `day`, ordenados por hora de inicio. */
export function eventsForDay(events: AgendaEvent[], day: Date): AgendaEvent[] {
  return events.filter((e) => isOnDay(e, day)).sort((a, b) => a.start_at.localeCompare(b.start_at));
}

// ── Helpers de grilla horaria (DayView / WeekView) ──────────────────────────

/** Hora decimal de un evento (ej. 10:30 → 10.5). Helper interno del módulo. */
function eventStartHour(event: AgendaEvent): number {
  const d = new Date(event.start_at);
  return d.getHours() + d.getMinutes() / 60;
}

/**
 * Top en px del evento dentro de la grilla (0 = hora de inicio de la grilla).
 * `H0` = primera hora visible (ej. 8), `rowPx` = px por hora.
 */
export function gridTop(event: AgendaEvent, H0: number, rowPx: number): number {
  return (eventStartHour(event) - H0) * rowPx;
}

/**
 * Altura en px del bloque del evento, mínimo `minPx`.
 * `rowPx` = px por hora.
 */
export function gridHeight(event: AgendaEvent, rowPx: number, minPx = 20): number {
  return Math.max(minPx, (event.duration_min / 60) * rowPx);
}

/** Hora decimal actual. */
export function nowHour(): number {
  const d = new Date();
  return d.getHours() + d.getMinutes() / 60;
}

/** ¿El evento cae (al menos parcialmente) en la ventana horaria [H0, H1]? */
export function isInRange(event: AgendaEvent, H0: number, H1: number): boolean {
  const start = eventStartHour(event);
  const end = start + event.duration_min / 60;
  return end > H0 && start < H1;
}

/**
 * Rango horario `[minH, maxH]` de una grilla: cubre la ventana base
 * `[baseH0, baseH1]` (por defecto 8–20h) y la **expande** para incluir todos
 * los eventos de `days` que caigan fuera (con `floor`/`ceil` a la hora), clamp
 * a `[0, 24]`. Cero recorte por la ventana base: ningún evento desaparece por
 * caer antes de `baseH0` o después de `baseH1`. (No resuelve el wrap de
 * medianoche: la cola post-00:00 de un evento pertenece al día siguiente.)
 * Compartido por DayView (`days = [day]`) y WeekView (`days` = los 7 de la semana).
 */
export function hourBounds(
  events: AgendaEvent[],
  days: Date[],
  baseH0 = 8,
  baseH1 = 20,
): { minH: number; maxH: number } {
  let minH = baseH0;
  let maxH = baseH1;
  for (const day of days) {
    for (const event of eventsForDay(events, day)) {
      const start = eventStartHour(event);
      const end = start + event.duration_min / 60;
      minH = Math.min(minH, Math.floor(start));
      maxH = Math.max(maxH, Math.ceil(end));
    }
  }
  return { minH: Math.max(0, minH), maxH: Math.min(24, maxH) };
}

/**
 * Intervalo (en minutos del día local) para el algoritmo de columnas de
 * `@ynara/core`. Permite acomodar lado-a-lado los eventos concurrentes.
 */
export function toLayoutInterval(event: AgendaEvent): LayoutInterval {
  const start = eventStartHour(event) * 60;
  return { id: event.id, start, end: start + event.duration_min };
}
