import { describe, expect, it } from "vitest";
import type { AgendaEvent } from "./api";
import {
  eventEnd,
  eventsForDay,
  formatEventRange,
  formatTime,
  gridHeight,
  gridTop,
  hourBounds,
  isInRange,
  isOnDay,
  monthGridDays,
  nowHour,
  startOfMonth,
  startOfWeek,
  weekDays,
} from "./format";

/**
 * `start_at` derivado de un `Date` **local** (no un ISO con offset fijo): así las
 * aserciones de hora local son independientes del huso donde corra el CI.
 */
const localISO = (y: number, mo: number, d: number, h: number, mi: number) =>
  new Date(y, mo, d, h, mi).toISOString();

const makeEvent = (
  overrides: Partial<AgendaEvent> & Pick<AgendaEvent, "start_at" | "duration_min">,
): AgendaEvent => ({
  id: "0193d001-0000-4000-8000-000000000001",
  title: "Bloque",
  mode: null,
  status: "confirmed",
  location: null,
  ...overrides,
});

describe("formatTime", () => {
  it("formatea la hora local como HH:MM con zero-pad", () => {
    expect(formatTime(localISO(2026, 4, 7, 14, 5))).toBe("14:05");
    expect(formatTime(localISO(2026, 4, 7, 9, 0))).toBe("09:00");
  });
});

describe("eventEnd / formatEventRange", () => {
  it("deriva el fin como inicio + duración", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 10, 0), duration_min: 90 });
    expect(eventEnd(ev).getHours()).toBe(11);
    expect(eventEnd(ev).getMinutes()).toBe(30);
  });

  it("arma el rango legible inicio – fin", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 10, 0), duration_min: 90 });
    expect(formatEventRange(ev)).toBe("10:00 – 11:30");
  });

  it("cruza la medianoche sin romperse", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 23, 30), duration_min: 60 });
    expect(formatEventRange(ev)).toBe("23:30 – 00:30");
  });
});

describe("startOfWeek", () => {
  it("devuelve el lunes 00:00 de la semana que contiene la fecha", () => {
    const d = new Date(2026, 4, 7, 15, 30);
    const monday = startOfWeek(d);
    expect(monday.getDay()).toBe(1); // lunes
    expect(monday.getHours()).toBe(0);
    expect(monday.getMinutes()).toBe(0);
    expect(monday.getTime()).toBeLessThanOrEqual(d.getTime());
    expect(d.getTime() - monday.getTime()).toBeLessThan(7 * 24 * 60 * 60 * 1000);
  });

  it("es idempotente sobre un lunes", () => {
    const monday = startOfWeek(new Date(2026, 4, 7, 12, 0));
    expect(startOfWeek(monday).getTime()).toBe(monday.getTime());
  });
});

describe("weekDays", () => {
  it("devuelve 7 días lunes→domingo a las 00:00", () => {
    const days = weekDays(new Date(2026, 4, 7, 9, 0));
    expect(days).toHaveLength(7);
    expect(days.map((d) => d.getDay())).toEqual([1, 2, 3, 4, 5, 6, 0]);
    expect(days.every((d) => d.getHours() === 0 && d.getMinutes() === 0)).toBe(true);
  });
});

describe("isOnDay / eventsForDay", () => {
  const day = new Date(2026, 4, 7, 0, 0);
  const morning = makeEvent({ start_at: localISO(2026, 4, 7, 9, 0), duration_min: 30 });
  const evening = makeEvent({
    id: "0193d001-0000-4000-8000-000000000002",
    start_at: localISO(2026, 4, 7, 18, 0),
    duration_min: 30,
  });
  const otherDay = makeEvent({
    id: "0193d001-0000-4000-8000-000000000003",
    start_at: localISO(2026, 4, 8, 9, 0),
    duration_min: 30,
  });

  it("isOnDay matchea solo el día local", () => {
    expect(isOnDay(morning, day)).toBe(true);
    expect(isOnDay(otherDay, day)).toBe(false);
  });

  it("eventsForDay filtra al día y ordena por inicio", () => {
    const result = eventsForDay([evening, otherDay, morning], day);
    expect(result.map((e) => e.start_at)).toEqual([morning.start_at, evening.start_at]);
  });
});

describe("gridTop / gridHeight / isInRange", () => {
  const ev = makeEvent({ start_at: localISO(2026, 4, 7, 10, 30), duration_min: 90 });

  it("gridTop posiciona correctamente respecto a H0", () => {
    // 10:30 − 8:00 = 2.5h * 52px = 130px
    expect(gridTop(ev, 8, 52)).toBeCloseTo(130, 1);
  });

  it("gridTop da 0 cuando el evento empieza justo en H0", () => {
    const ev0 = makeEvent({ start_at: localISO(2026, 4, 7, 8, 0), duration_min: 60 });
    expect(gridTop(ev0, 8, 52)).toBe(0);
  });

  it("gridHeight calcula en función de la duración", () => {
    // 90min / 60 * 52px = 78px
    expect(gridHeight(ev, 52)).toBeCloseTo(78, 1);
  });

  it("gridHeight respeta el mínimo", () => {
    const corto = makeEvent({ start_at: localISO(2026, 4, 7, 10, 0), duration_min: 5 });
    expect(gridHeight(corto, 52, 20)).toBe(20);
  });

  it("isInRange verdadero cuando el evento está en la ventana", () => {
    expect(isInRange(ev, 8, 20)).toBe(true);
  });

  it("isInRange falso para evento completamente fuera", () => {
    const tarde = makeEvent({ start_at: localISO(2026, 4, 7, 21, 0), duration_min: 60 });
    expect(isInRange(tarde, 8, 20)).toBe(false);
  });
});

describe("nowHour", () => {
  it("devuelve un número entre 0 y 24", () => {
    const h = nowHour();
    expect(h).toBeGreaterThanOrEqual(0);
    expect(h).toBeLessThan(24);
  });
});

describe("hourBounds", () => {
  const day = new Date(2026, 4, 7, 0, 0);

  it("sin eventos devuelve la ventana base 8–20h", () => {
    expect(hourBounds([], [day])).toEqual({ minH: 8, maxH: 20 });
  });

  it("eventos dentro de 8–20h no cambian la ventana", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 9, 0), duration_min: 60 });
    expect(hourBounds([ev], [day])).toEqual({ minH: 8, maxH: 20 });
  });

  it("un evento de madrugada baja minH (floor)", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 6, 30), duration_min: 30 });
    expect(hourBounds([ev], [day])).toEqual({ minH: 6, maxH: 20 });
  });

  it("un evento de noche sube maxH (ceil)", () => {
    const ev = makeEvent({ start_at: localISO(2026, 4, 7, 21, 0), duration_min: 90 });
    expect(hourBounds([ev], [day])).toEqual({ minH: 8, maxH: 23 });
  });

  it("clampea a [0, 24]", () => {
    const madrugada = makeEvent({ start_at: localISO(2026, 4, 7, 0, 0), duration_min: 30 });
    const trasnoche = makeEvent({
      id: "0193d001-0000-4000-8000-0000000000a2",
      start_at: localISO(2026, 4, 7, 23, 30),
      duration_min: 30,
    });
    expect(hourBounds([madrugada, trasnoche], [day])).toEqual({ minH: 0, maxH: 24 });
  });

  it("sobre varios días toma la unión (caso semana)", () => {
    const lunesTemprano = makeEvent({ start_at: localISO(2026, 4, 4, 7, 0), duration_min: 30 });
    const martesTarde = makeEvent({
      id: "0193d001-0000-4000-8000-0000000000a3",
      start_at: localISO(2026, 4, 5, 21, 0),
      duration_min: 60,
    });
    const days = [new Date(2026, 4, 4), new Date(2026, 4, 5)];
    expect(hourBounds([lunesTemprano, martesTarde], days)).toEqual({ minH: 7, maxH: 22 });
  });

  it("respeta una ventana base custom", () => {
    expect(hourBounds([], [day], 0, 24)).toEqual({ minH: 0, maxH: 24 });
  });
});

describe("startOfMonth", () => {
  it("devuelve el día 1 a las 00:00 del mes de la fecha", () => {
    const d = startOfMonth(new Date(2026, 4, 17, 15, 30));
    expect(d.getDate()).toBe(1);
    expect(d.getMonth()).toBe(4);
    expect(d.getFullYear()).toBe(2026);
    expect(d.getHours()).toBe(0);
    expect(d.getMinutes()).toBe(0);
  });
});

describe("monthGridDays", () => {
  it("devuelve 42 días (6 semanas) de lunes a domingo", () => {
    const days = monthGridDays(new Date(2026, 4, 17));
    expect(days).toHaveLength(42);
    expect(days[0]?.getDay()).toBe(1); // lunes
    expect(days[41]?.getDay()).toBe(0); // domingo
  });

  it("la grilla arranca en el lunes de la semana del día 1", () => {
    const days = monthGridDays(new Date(2026, 4, 17));
    const first = days[0];
    expect(first?.getDay()).toBe(1);
    const firstOfMonth = new Date(2026, 4, 1).getTime();
    expect(first?.getTime()).toBeLessThanOrEqual(firstOfMonth);
    expect(firstOfMonth - (first?.getTime() ?? 0)).toBeLessThan(7 * 24 * 60 * 60 * 1000);
  });

  it("cubre todos los días del mes (mayo: 31)", () => {
    const days = monthGridDays(new Date(2026, 4, 17));
    const inMonth = days.filter((d) => d.getMonth() === 4 && d.getFullYear() === 2026);
    expect(inMonth).toHaveLength(31);
    const nums = inMonth.map((d) => d.getDate());
    expect(nums).toContain(1);
    expect(nums).toContain(31);
  });
});
