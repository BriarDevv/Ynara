import type { Task } from "@ynara/shared-schemas";

/**
 * Formateo del dashboard Hoy (build-plan Fase E). Todo recibe `now`/la fecha por
 * parámetro para ser testeable sin mockear el reloj (igual que `lib/time.ts`).
 * Locale fijo `es-AR` para que las fechas salgan en español rioplatense con
 * mayúscula inicial editorial ("Martes, 7 de mayo").
 */

const LOCALE = "es-AR";

const DATE_FMT = new Intl.DateTimeFormat(LOCALE, {
  weekday: "long",
  day: "numeric",
  month: "long",
});

const CLOCK_FMT = new Intl.DateTimeFormat(LOCALE, {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** Primera letra a mayúscula (Intl devuelve "martes, 7 de mayo"). */
function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Fecha larga del header: "Martes, 7 de mayo". */
export function formatHoyDate(now: Date): string {
  return capitalize(DATE_FMT.format(now));
}

/**
 * Saludo según la hora local (wireframe 06 / mockup): "Buen día" hasta el
 * mediodía, "Buenas tardes" hasta las 20h, "Buenas noches" después. El nombre
 * lo agrega el header (`${greet(now)}, ${nombre}.`).
 */
export function greet(now: Date): string {
  const h = now.getHours();
  if (h < 12) return "Buen día";
  if (h < 20) return "Buenas tardes";
  return "Buenas noches";
}

/** Reloj corto "15:30" (variante Hoy vacío, wireframe 07). */
export function formatClock(now: Date): string {
  return CLOCK_FMT.format(now);
}

/**
 * Meta de una prioridad bajo el título:
 *  - hecha → "09:15 · completada" (o sólo "completada" si no tiene horario).
 *  - pendiente → "14:00 · 45 min" (horario y/o duración, lo que haya).
 *
 * Devuelve `""` si no hay nada que mostrar (tarea pendiente sin horario ni
 * duración): el caller decide no renderizar la meta.
 */
export function formatTaskMeta(task: Task): string {
  const clock = task.scheduled_at ? CLOCK_FMT.format(new Date(task.scheduled_at)) : null;
  if (task.status === "done") {
    return clock ? `${clock} · completada` : "completada";
  }
  const duration = task.duration_min !== null ? `${task.duration_min} min` : null;
  return [clock, duration].filter(Boolean).join(" · ");
}
