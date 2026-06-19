import { describe, expect, it } from "vitest";

import {
  AgendaEventSchema,
  EventCreateSchema,
  EventPatchSchema,
  EventsResponseSchema,
} from "./agenda";

const ISO = "2026-05-07T14:00:00+00:00";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const event = {
  id: UUID,
  title: "Reunión con cátedra",
  start_at: ISO,
  duration_min: 45,
  mode: "productividad" as const,
  status: "confirmed" as const,
  location: "Aula 3",
};

describe("AgendaEventSchema", () => {
  it("acepta un evento completo", () => {
    expect(AgendaEventSchema.parse(event)).toEqual(event);
  });

  it("permite modo y location nulos (evento transversal sin lugar)", () => {
    const parsed = AgendaEventSchema.parse({ ...event, mode: null, location: null });
    expect(parsed.mode).toBeNull();
    expect(parsed.location).toBeNull();
  });

  it("rechaza título vacío", () => {
    expect(() => AgendaEventSchema.parse({ ...event, title: "" })).toThrow();
  });

  it("rechaza duración no positiva", () => {
    expect(() => AgendaEventSchema.parse({ ...event, duration_min: 0 })).toThrow();
  });

  it("rechaza estado fuera del enum", () => {
    expect(() => AgendaEventSchema.parse({ ...event, status: "archived" })).toThrow();
  });

  it("rechaza start_at sin offset", () => {
    expect(() => AgendaEventSchema.parse({ ...event, start_at: "2026-05-07T14:00:00" })).toThrow();
  });

  it("acepta los campos de calendario v2 (time_zone, all_day, recurrence)", () => {
    const parsed = AgendaEventSchema.parse({
      ...event,
      time_zone: "America/Argentina/Buenos_Aires",
      all_day: false,
      recurrence: ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
    });
    expect(parsed.time_zone).toBe("America/Argentina/Buenos_Aires");
    expect(parsed.all_day).toBe(false);
    expect(parsed.recurrence).toEqual(["RRULE:FREQ=WEEKLY;BYDAY=MO"]);
  });

  it("los campos v2 son opcionales (back-compat con el mock)", () => {
    const parsed = AgendaEventSchema.parse(event);
    expect(parsed).not.toHaveProperty("recurrence");
    expect(parsed.time_zone).toBeUndefined();
  });

  it("acepta recurrence null (evento único explícito)", () => {
    expect(AgendaEventSchema.parse({ ...event, recurrence: null }).recurrence).toBeNull();
  });

  it("rechaza recurrence que no sea array de strings", () => {
    expect(() => AgendaEventSchema.parse({ ...event, recurrence: "RRULE:FREQ=DAILY" })).toThrow();
  });

  it("rechaza all_day no booleano", () => {
    expect(() => AgendaEventSchema.parse({ ...event, all_day: "si" })).toThrow();
  });

  it("rechaza recurrence sin time_zone (invariante DST del ADR-018)", () => {
    expect(() => AgendaEventSchema.parse({ ...event, recurrence: ["RRULE:FREQ=DAILY"] })).toThrow();
  });

  it("acepta recurrence cuando trae time_zone", () => {
    const parsed = AgendaEventSchema.parse({
      ...event,
      time_zone: "America/Argentina/Buenos_Aires",
      recurrence: ["RRULE:FREQ=DAILY"],
    });
    expect(parsed.recurrence).toHaveLength(1);
  });
});

describe("EventsResponseSchema", () => {
  it("parsea items + total", () => {
    const parsed = EventsResponseSchema.parse({ items: [event], total: 1 });
    expect(parsed.items).toHaveLength(1);
    expect(parsed.total).toBe(1);
  });

  it("acepta lista vacía", () => {
    expect(EventsResponseSchema.parse({ items: [], total: 0 }).items).toEqual([]);
  });

  it("rechaza total negativo", () => {
    expect(() => EventsResponseSchema.parse({ items: [], total: -1 })).toThrow();
  });
});

describe("EventCreateSchema", () => {
  it("acepta el form mínimo (título + inicio + duración)", () => {
    const parsed = EventCreateSchema.parse({
      title: "Estudiar cap. 3",
      start_at: ISO,
      duration_min: 90,
    });
    expect(parsed.title).toBe("Estudiar cap. 3");
    expect(parsed.mode).toBeUndefined();
  });

  it("acepta mode y location opcionales", () => {
    const parsed = EventCreateSchema.parse({
      title: "x",
      start_at: ISO,
      duration_min: 30,
      mode: "estudio",
      location: "Biblioteca",
    });
    expect(parsed.mode).toBe("estudio");
  });

  it("rechaza un create sin título", () => {
    expect(() => EventCreateSchema.parse({ start_at: ISO, duration_min: 30 })).toThrow();
  });

  it("acepta los campos de calendario v2 (time_zone, recurrence)", () => {
    const parsed = EventCreateSchema.parse({
      title: "Clase semanal",
      start_at: ISO,
      duration_min: 60,
      time_zone: "America/Argentina/Buenos_Aires",
      recurrence: ["RRULE:FREQ=WEEKLY;COUNT=10"],
    });
    expect(parsed.recurrence).toHaveLength(1);
    expect(parsed.time_zone).toBe("America/Argentina/Buenos_Aires");
  });
});

describe("EventPatchSchema", () => {
  it("acepta un patch parcial", () => {
    expect(EventPatchSchema.parse({ status: "cancelled" })).toEqual({ status: "cancelled" });
  });

  it("acepta un patch vacío (no-op)", () => {
    expect(EventPatchSchema.parse({})).toEqual({});
  });

  it("rechaza un campo con valor inválido", () => {
    expect(() => EventPatchSchema.parse({ duration_min: -5 })).toThrow();
  });
});
