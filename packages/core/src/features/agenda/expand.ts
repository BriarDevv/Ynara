/**
 * **Expansión de recurrencia** (CALENDAR-RESEARCH-2026 §1.3, ADR-023). Convierte
 * un `AgendaEvent` (único o recurrente) en las **instancias concretas** que caen
 * en un rango `[from, to]`, listo para renderizar o servir desde `/v1/events`.
 *
 * Pura y platform-agnostic (web + mobile + backend la consumen). El engine es
 * `rrule-temporal` sobre `Temporal` (wall-clock + TZID), que NO se corre en los
 * cambios de DST — el motivo por el que `recurrence` exige `time_zone`
 * (invariante del schema). En RN/Hermes corre con `@js-temporal/polyfill`
 * (spike pendiente — ver guía mobile).
 */

import { Temporal } from "@js-temporal/polyfill";
import type { AgendaEvent } from "@ynara/shared-schemas";
import { RRuleTemporal } from "rrule-temporal";

const MS_PER_MIN = 60_000;

/** Rango `[from, to]` (ISO con offset) sobre el que se expande. */
export type DateRange = {
  from: string;
  to: string;
};

/** Una instancia concreta de un evento dentro del rango. */
export type CalendarInstance = {
  /** Evento madre (la serie, o el evento único). */
  master: AgendaEvent;
  /** Inicio concreto de esta instancia (ISO con offset). El fin se deriva de `master.duration_min`. */
  start_at: string;
  /** `true` si la generó la recurrencia; `false` si es el evento único. */
  recurring: boolean;
};

/** ¿El bloque `[start, start+dur]` solapa el rango `[from, to)`? */
function overlaps(startIso: string, durationMin: number, from: number, to: number): boolean {
  const start = new Date(startIso).getTime();
  const end = start + durationMin * MS_PER_MIN;
  return start < to && end > from;
}

/** `ZonedDateTime` → `YYYYMMDDTHHMMSS` (wall-clock local; el TZID da el huso). */
function formatDtstart(zdt: Temporal.ZonedDateTime): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${zdt.year}${p(zdt.month)}${p(zdt.day)}T${p(zdt.hour)}${p(zdt.minute)}${p(zdt.second)}`;
}

/**
 * Expande un evento a sus instancias en `[from, to]`.
 *
 * - **Único** (`recurrence` null/vacío): devuelve `[el evento]` si solapa el rango.
 * - **Recurrente**: arma el `DTSTART;TZID=…` desde `start_at`+`time_zone`, le suma
 *   las líneas `recurrence` (RRULE/RDATE/EXDATE) y expande con `rrule-temporal`,
 *   filtrando las instancias que realmente solapan el rango.
 *
 * TODO(all_day): hoy se expanden como timed a medianoche y `duration_min` cuenta
 * minutos, no días — el `VALUE=DATE` + duración-en-días queda como refinamiento
 * (CALENDAR-PLAN.md, Fases 4/5). No hay consumidor de `all_day` recurrente aún.
 */
export function expand(event: AgendaEvent, range: DateRange): CalendarInstance[] {
  const from = new Date(range.from).getTime();
  const to = new Date(range.to).getTime();
  const rec = event.recurrence;

  if (!rec || rec.length === 0) {
    return overlaps(event.start_at, event.duration_min, from, to)
      ? [{ master: event, start_at: event.start_at, recurring: false }]
      : [];
  }

  // El schema garantiza `time_zone` cuando hay `recurrence`; guard defensivo.
  const tz = event.time_zone;
  if (!tz) throw new Error("expand: evento recurrente sin time_zone");

  const zdtStart = Temporal.Instant.from(event.start_at).toZonedDateTimeISO(tz);
  const rruleString = [`DTSTART;TZID=${tz}:${formatDtstart(zdtStart)}`, ...rec].join("\n");
  const rule = new RRuleTemporal({ rruleString });

  // Ampliamos el `after` por la duración para no perder ocurrencias que
  // empezaron antes de `from` pero siguen activas dentro del rango. El borde
  // derecho lo decide `overlaps` (half-open `start < to`), no el `inc` de
  // `between` → lo dejamos en `false` para no contradecir esa semántica.
  const after = new Date(from - event.duration_min * MS_PER_MIN);
  return rule
    .between(after, new Date(to), false)
    .map(
      (zdt): CalendarInstance => ({
        master: event,
        start_at: zdt.toString({ timeZoneName: "never" }),
        recurring: true,
      }),
    )
    .filter((inst) => overlaps(inst.start_at, event.duration_min, from, to));
}

/**
 * Expande una lista de eventos a todas sus instancias en `[from, to]`, ordenadas
 * por inicio. Es lo que devolvería `GET /v1/events?from&to` (instancias ya
 * expandidas) y lo que consumen las vistas.
 */
export function expandAll(events: readonly AgendaEvent[], range: DateRange): CalendarInstance[] {
  return events
    .flatMap((event) => expand(event, range))
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
}
