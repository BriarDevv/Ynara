import type { AgendaEvent } from "@ynara/core/features/agenda";
import { describe, expect, it } from "vitest";
import {
  eventEnd,
  eventsForDay,
  formatDayLong,
  formatDayNum,
  formatEventRange,
  formatTime,
  formatWeekdayShort,
  formatWeekRange,
  isOnDay,
  isSameDay,
  startOfWeek,
  weekDays,
} from "./format";

/**
 * Tests de los helpers puros de fecha de la Agenda. Determinismo:
 * - Las funciones que operan sobre `Date` se prueban con `new Date(año, mes, día)`
 *   (hora local) → independientes de la timezone del runner.
 * - Las que parsean ISO (`formatTime`/`eventEnd`/`formatEventRange`) reciben el
 *   ISO vía `local.toISOString()`: el instante se codifica en UTC y se relee en
 *   la misma TZ local, así el round-trip es estable en cualquier máquina.
 *
 * Ancla de calendario: el **5-ene-2026 es lunes** (2026-01-01 = jueves), de donde
 * salen los lunes conocidos usados abajo (6-abr y 27-abr-2026).
 */

/** Evento mínimo válido a partir de un inicio local. */
function makeEvent(
  start: Date,
  durationMin = 45,
  overrides: Partial<AgendaEvent> = {},
): AgendaEvent {
  return {
    id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    title: "Evento",
    start_at: start.toISOString(),
    duration_min: durationMin,
    mode: "productividad",
    status: "confirmed",
    location: null,
    ...overrides,
  };
}

describe("formatTime", () => {
  it("formatea hora local HH:MM", () => {
    expect(formatTime(new Date(2026, 4, 7, 14, 30).toISOString())).toBe("14:30");
  });

  it("rellena con cero a la izquierda", () => {
    expect(formatTime(new Date(2026, 4, 7, 9, 5).toISOString())).toBe("09:05");
  });
});

describe("eventEnd", () => {
  it("suma la duración al inicio", () => {
    const end = eventEnd(makeEvent(new Date(2026, 4, 7, 10, 0), 90));
    expect(end.getHours()).toBe(11);
    expect(end.getMinutes()).toBe(30);
  });
});

describe("formatEventRange", () => {
  it("arma el rango inicio – fin", () => {
    expect(formatEventRange(makeEvent(new Date(2026, 4, 7, 10, 0), 90))).toBe("10:00 – 11:30");
  });

  it("rellena ambos extremos", () => {
    expect(formatEventRange(makeEvent(new Date(2026, 4, 7, 9, 5), 30))).toBe("09:05 – 09:35");
  });
});

describe("startOfWeek", () => {
  it("desde un miércoles vuelve al lunes de esa semana", () => {
    const monday = startOfWeek(new Date(2026, 0, 7, 15, 0)); // mié 7-ene-2026
    expect(monday.getFullYear()).toBe(2026);
    expect(monday.getMonth()).toBe(0);
    expect(monday.getDate()).toBe(5); // lun 5-ene
    expect(monday.getDay()).toBe(1);
  });

  it("desde un lunes devuelve el mismo día", () => {
    expect(startOfWeek(new Date(2026, 0, 5)).getDate()).toBe(5);
  });

  it("desde un domingo vuelve al lunes anterior (cruza de año)", () => {
    const monday = startOfWeek(new Date(2026, 0, 4)); // dom 4-ene-2026
    expect(monday.getFullYear()).toBe(2025);
    expect(monday.getMonth()).toBe(11);
    expect(monday.getDate()).toBe(29); // lun 29-dic-2025
  });

  it("normaliza la hora a 00:00:00.000", () => {
    const monday = startOfWeek(new Date(2026, 0, 7, 23, 59, 59, 999));
    expect([
      monday.getHours(),
      monday.getMinutes(),
      monday.getSeconds(),
      monday.getMilliseconds(),
    ]).toEqual([0, 0, 0, 0]);
  });
});

describe("weekDays", () => {
  it("devuelve 7 días de lunes a domingo a las 00:00", () => {
    const days = weekDays(new Date(2026, 0, 7)); // semana del 5-ene
    expect(days).toHaveLength(7);
    expect(days[0].getDate()).toBe(5);
    expect(days[0].getDay()).toBe(1); // lunes
    expect(days[6].getDate()).toBe(11);
    expect(days[6].getDay()).toBe(0); // domingo
    expect(days.every((d) => d.getHours() === 0)).toBe(true);
  });
});

describe("isOnDay", () => {
  const event = makeEvent(new Date(2026, 4, 7, 14, 0));

  it("true si el evento cae en el día", () => {
    expect(isOnDay(event, new Date(2026, 4, 7))).toBe(true);
  });

  it("false si es otro día", () => {
    expect(isOnDay(event, new Date(2026, 4, 8))).toBe(false);
  });
});

describe("eventsForDay", () => {
  it("filtra por día y ordena por hora de inicio", () => {
    const tarde = makeEvent(new Date(2026, 4, 7, 14, 0), 45, { id: "tarde" });
    const manana = makeEvent(new Date(2026, 4, 7, 9, 0), 45, { id: "manana" });
    const otroDia = makeEvent(new Date(2026, 4, 8, 10, 0), 45, { id: "otro" });

    const result = eventsForDay([tarde, manana, otroDia], new Date(2026, 4, 7));
    expect(result.map((e) => e.id)).toEqual(["manana", "tarde"]);
  });
});

describe("isSameDay", () => {
  it("true mismo día con distinta hora", () => {
    expect(isSameDay(new Date(2026, 4, 7, 9, 0), new Date(2026, 4, 7, 23, 0))).toBe(true);
  });

  it("false en días distintos", () => {
    expect(isSameDay(new Date(2026, 4, 7), new Date(2026, 4, 8))).toBe(false);
  });

  it("false mismo número de día pero otro mes", () => {
    expect(isSameDay(new Date(2026, 4, 7), new Date(2026, 5, 7))).toBe(false);
  });
});

describe("etiquetas de fecha", () => {
  it("formatWeekdayShort", () => {
    expect(formatWeekdayShort(new Date(2026, 0, 5))).toBe("Lun"); // lunes
    expect(formatWeekdayShort(new Date(2026, 0, 4))).toBe("Dom"); // domingo
  });

  it("formatDayNum", () => {
    expect(formatDayNum(new Date(2026, 4, 7))).toBe("7");
  });

  it("formatDayLong", () => {
    expect(formatDayLong(new Date(2026, 0, 5))).toBe("Lunes, 5 de enero");
  });
});

describe("formatWeekRange", () => {
  it("dentro del mismo mes", () => {
    const monday = new Date(2026, 3, 6); // lun 6-abr-2026
    expect(monday.getDay()).toBe(1); // precondición: es lunes
    expect(formatWeekRange(monday)).toBe("6 – 12 de abril");
  });

  it("cruzando de mes", () => {
    const monday = new Date(2026, 3, 27); // lun 27-abr-2026
    expect(monday.getDay()).toBe(1); // precondición: es lunes
    expect(formatWeekRange(monday)).toBe("27 de abril – 3 de mayo");
  });
});
