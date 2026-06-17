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

/** Hora decimal de un evento (ej. 10:30 → 10.5). */
export function eventStartHour(event: AgendaEvent): number {
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
