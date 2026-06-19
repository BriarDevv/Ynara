import { Temporal } from "@js-temporal/polyfill";
import type { AgendaEvent } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";

import { expand, expandAll } from "./expand";

const base: AgendaEvent = {
  id: "0193e001-0000-4000-8000-000000000001",
  title: "Evento",
  start_at: "2026-05-04T09:00:00+00:00",
  duration_min: 60,
  mode: null,
  status: "confirmed",
  location: null,
};

const makeEvent = (overrides: Partial<AgendaEvent>): AgendaEvent => ({ ...base, ...overrides });

/** Hora local (wall-clock) de un ISO en un huso, para chequear DST. */
const localHour = (iso: string, tz: string) =>
  Temporal.Instant.from(iso).toZonedDateTimeISO(tz).hour;

describe("expand — evento único", () => {
  it("devuelve el evento si solapa el rango", () => {
    const out = expand(base, {
      from: "2026-05-04T00:00:00+00:00",
      to: "2026-05-05T00:00:00+00:00",
    });
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ start_at: base.start_at, recurring: false, master: base });
  });

  it("no lo devuelve si cae fuera del rango", () => {
    const out = expand(base, {
      from: "2026-06-01T00:00:00+00:00",
      to: "2026-06-02T00:00:00+00:00",
    });
    expect(out).toHaveLength(0);
  });

  it("incluye un evento que empezó antes pero sigue activo en el rango", () => {
    // Empieza 08:30, dura 60 → termina 09:30; el rango arranca 09:00.
    const ev = makeEvent({ start_at: "2026-05-04T08:30:00+00:00", duration_min: 60 });
    const out = expand(ev, { from: "2026-05-04T09:00:00+00:00", to: "2026-05-04T12:00:00+00:00" });
    expect(out).toHaveLength(1);
  });
});

describe("expand — recurrencia", () => {
  it("expande una regla diaria con COUNT", () => {
    const ev = makeEvent({
      start_at: "2026-05-04T09:00:00+00:00",
      time_zone: "UTC",
      recurrence: ["RRULE:FREQ=DAILY;COUNT=3"],
    });
    const out = expand(ev, { from: "2026-05-04T00:00:00+00:00", to: "2026-05-07T00:00:00+00:00" });
    expect(out).toHaveLength(3);
    expect(out.every((i) => i.recurring)).toBe(true);
    expect(out.map((i) => i.start_at.slice(0, 10))).toEqual([
      "2026-05-04",
      "2026-05-05",
      "2026-05-06",
    ]);
  });

  it("acota al rango pedido (no devuelve instancias fuera)", () => {
    const ev = makeEvent({
      start_at: "2026-05-04T09:00:00+00:00",
      time_zone: "UTC",
      recurrence: ["RRULE:FREQ=DAILY"], // infinita
    });
    const out = expand(ev, { from: "2026-05-10T00:00:00+00:00", to: "2026-05-13T00:00:00+00:00" });
    expect(out.map((i) => i.start_at.slice(0, 10))).toEqual([
      "2026-05-10",
      "2026-05-11",
      "2026-05-12",
    ]);
  });

  it("respeta EXDATE (excluye una ocurrencia)", () => {
    const ev = makeEvent({
      start_at: "2026-05-04T09:00:00+00:00",
      time_zone: "UTC",
      recurrence: ["RRULE:FREQ=DAILY;COUNT=3", "EXDATE;TZID=UTC:20260505T090000"],
    });
    const out = expand(ev, { from: "2026-05-04T00:00:00+00:00", to: "2026-05-07T00:00:00+00:00" });
    expect(out.map((i) => i.start_at.slice(0, 10))).toEqual(["2026-05-04", "2026-05-06"]);
  });

  it("**mantiene el wall-clock a través de un cambio de DST** (no se corre la hora)", () => {
    // America/New_York: spring-forward el 8-mar-2026. Lunes 09:00 semanal desde
    // el 2-mar (EST). Las ocurrencias posteriores caen en EDT, pero siguen 09:00.
    const tz = "America/New_York";
    const ev = makeEvent({
      start_at: "2026-03-02T09:00:00-05:00",
      time_zone: tz,
      recurrence: ["RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=4"],
    });
    const out = expand(ev, { from: "2026-03-01T00:00:00-05:00", to: "2026-03-31T00:00:00-04:00" });
    expect(out).toHaveLength(4);
    // Todas a las 09:00 locales, aunque el offset (UTC) cambie por el DST.
    expect(out.every((i) => localHour(i.start_at, tz) === 9)).toBe(true);
    // El primero es EST (-05:00); uno posterior ya es EDT (-04:00).
    expect(out[0]?.start_at).toContain("-05:00");
    expect(out.some((i) => i.start_at.includes("-04:00"))).toBe(true);
  });

  it("lanza si un recurrente llega sin time_zone (guard defensivo)", () => {
    const ev = makeEvent({ recurrence: ["RRULE:FREQ=DAILY"], time_zone: null });
    expect(() => expand(ev, { from: base.start_at, to: "2026-05-10T00:00:00+00:00" })).toThrow();
  });
});

describe("expandAll", () => {
  it("aplana y ordena las instancias de varios eventos por inicio", () => {
    const a = makeEvent({ id: "a", start_at: "2026-05-04T15:00:00+00:00" });
    const b = makeEvent({ id: "b", start_at: "2026-05-04T09:00:00+00:00" });
    const out = expandAll([a, b], {
      from: "2026-05-04T00:00:00+00:00",
      to: "2026-05-05T00:00:00+00:00",
    });
    expect(out.map((i) => i.master.id)).toEqual(["b", "a"]);
  });
});
