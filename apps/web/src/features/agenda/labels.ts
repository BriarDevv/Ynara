/**
 * Etiquetas i18n de la Agenda (`es-AR`): día largo, rango de semana y celdas
 * del calendario. Separadas de `format.ts` (matemática de fechas pura) porque
 * acá manda `Intl.DateTimeFormat` — presentación, no lógica. Locale fijo para
 * que las fechas salgan en español rioplatense, mayúscula inicial editorial.
 */

const LOCALE = "es-AR";

const DAY_LONG_FMT = new Intl.DateTimeFormat(LOCALE, {
  weekday: "long",
  day: "numeric",
  month: "long",
});
const WEEKDAY_SHORT_FMT = new Intl.DateTimeFormat(LOCALE, { weekday: "short" });
const DAY_NUM_FMT = new Intl.DateTimeFormat(LOCALE, { day: "numeric" });
const DAY_MONTH_FMT = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long" });

/** Primera letra a mayúscula (Intl devuelve "martes, 7 de mayo"). */
function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Fecha larga de la vista día: "Martes, 7 de mayo". */
export function formatDayLong(day: Date): string {
  return capitalize(DAY_LONG_FMT.format(day));
}

/** Día de la semana corto y capitalizado, sin punto: "Lun" (cabecera de columna). */
export function formatWeekdayShort(day: Date): string {
  return capitalize(WEEKDAY_SHORT_FMT.format(day).replace(/\.$/, ""));
}

/** Número de día del mes: "7". */
export function formatDayNum(day: Date): string {
  return DAY_NUM_FMT.format(day);
}

/**
 * Rango de la semana a partir de su lunes: "5 – 11 de mayo" si no cruza de mes,
 * "28 de abril – 4 de mayo" si lo cruza.
 */
export function formatWeekRange(monday: Date): string {
  const sunday = new Date(monday);
  sunday.setDate(sunday.getDate() + 6);
  if (monday.getMonth() === sunday.getMonth()) {
    return `${DAY_NUM_FMT.format(monday)} – ${DAY_MONTH_FMT.format(sunday)}`;
  }
  return `${DAY_MONTH_FMT.format(monday)} – ${DAY_MONTH_FMT.format(sunday)}`;
}

/** ¿`a` y `b` son el mismo día local? (para marcar "hoy"). */
export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
