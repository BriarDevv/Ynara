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
