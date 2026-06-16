import type { Task } from "@ynara/shared-schemas";

/**
 * Formateo del dashboard Hoy (mobile) — espejo de
 * `apps/web/src/features/today/format.ts`, pero **Hermes-safe**: sin `Intl`
 * (como `lib/relativeTime.ts`), con los nombres en español rioplatense por
 * arrays. Todo recibe la fecha por parámetro para ser testeable sin mockear el
 * reloj. La hora se muestra en zona local (igual que web).
 */

const WEEKDAYS = [
  "Domingo",
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
] as const;

const MONTHS = [
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

/** Dos dígitos con cero a la izquierda ("9" → "09"). */
function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Fecha larga del header: "Martes, 7 de mayo". */
export function formatHoyDate(now: Date): string {
  return `${WEEKDAYS[now.getDay()]}, ${now.getDate()} de ${MONTHS[now.getMonth()]}`;
}

/** Reloj corto 24h "15:30" (hora local). */
export function formatClock(date: Date): string {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

/**
 * Meta de una prioridad bajo el título:
 *  - hecha → "09:15 · completada" (o sólo "completada" si no tiene horario).
 *  - pendiente → "14:00 · 45 min" (horario y/o duración, lo que haya).
 *
 * Devuelve `""` si no hay nada que mostrar (pendiente sin horario ni duración):
 * el caller decide no renderizar la meta.
 */
export function formatTaskMeta(task: Task): string {
  const clock = task.scheduled_at ? formatClock(new Date(task.scheduled_at)) : null;
  if (task.status === "done") {
    return clock ? `${clock} · completada` : "completada";
  }
  const duration = task.duration_min !== null ? `${task.duration_min} min` : null;
  return [clock, duration].filter(Boolean).join(" · ");
}
