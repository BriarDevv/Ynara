import type { AgendaEvent } from "@ynara/core/features/agenda";

/**
 * Helpers puros de presentación de la Agenda (mobile) — espejo de
 * `apps/web/src/features/agenda/format.ts`. Matemática de fechas pura, sin
 * presentación de etiquetas (eso va en `labels.ts`). Hermes-safe: sin Intl
 * (las etiquetas de vista larga sí usan Intl, pero en labels.ts).
 * Todo opera en **hora local** (igual que web).
 */

const MS_PER_MIN = 60_000;

/** Dos dígitos con cero a la izquierda ("9" → "09"). */
function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function hhmm(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
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

/** ¿`a` y `b` son el mismo día local? (para marcar "hoy"). */
export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

// ---------- Arrays Hermes-safe para labels (sin Intl en RN) ----------

const WEEKDAYS_LONG = [
  "Domingo",
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
] as const;

const WEEKDAYS_SHORT = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"] as const;

const MONTHS_LONG = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
] as const;

/** Cabecera de columna semana: "Lun", "Mar", … */
export function formatWeekdayShort(day: Date): string {
  return WEEKDAYS_SHORT[day.getDay()];
}

/** Número de día del mes: "7". */
export function formatDayNum(day: Date): string {
  return String(day.getDate());
}

/** Fecha larga de la vista día: "Martes, 7 de mayo". */
export function formatDayLong(day: Date): string {
  return `${WEEKDAYS_LONG[day.getDay()]}, ${day.getDate()} de ${MONTHS_LONG[day.getMonth()]}`;
}

/**
 * Rango de la semana a partir de su lunes: "5 – 11 de mayo" si no cruza de mes,
 * "28 de abril – 4 de mayo" si lo cruza.
 */
export function formatWeekRange(monday: Date): string {
  const sunday = new Date(monday);
  sunday.setDate(sunday.getDate() + 6);
  const startDay = monday.getDate();
  const endDay = sunday.getDate();
  const startMonth = MONTHS_LONG[monday.getMonth()];
  const endMonth = MONTHS_LONG[sunday.getMonth()];
  if (monday.getMonth() === sunday.getMonth()) {
    return `${startDay} – ${endDay} de ${endMonth}`;
  }
  return `${startDay} de ${startMonth} – ${endDay} de ${endMonth}`;
}
