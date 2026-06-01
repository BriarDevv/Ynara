import type { Task } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { formatClock, formatHoyDate, formatTaskMeta } from "./format";

// Construimos las fechas en hora local (new Date(y,m,d,h,m)) para que el
// round-trip ISO → formatClock devuelva la misma hora sin importar la TZ del
// runner.
const at = (h: number, m: number) => new Date(2026, 4, 7, h, m).toISOString();

const baseTask: Task = {
  id: "0193c001-0000-4000-8000-000000000002",
  title: "Llamada con equipo de diseño",
  status: "pending",
  scheduled_at: at(14, 0),
  duration_min: 45,
};

describe("formatHoyDate", () => {
  it("capitaliza la primera letra (Intl la devuelve en minúscula)", () => {
    const out = formatHoyDate(new Date(2026, 4, 7, 10, 0));
    expect(out[0]).toBe(out[0]?.toUpperCase());
    expect(out).toContain("7");
    expect(out).toContain("mayo");
  });
});

describe("formatClock", () => {
  it("formatea 24h como HH:MM", () => {
    expect(formatClock(new Date(2026, 4, 7, 15, 30))).toBe("15:30");
    expect(formatClock(new Date(2026, 4, 7, 9, 5))).toBe("09:05");
  });
});

describe("formatTaskMeta", () => {
  it("pendiente con horario + duración → 'HH:MM · N min'", () => {
    expect(formatTaskMeta(baseTask)).toBe("14:00 · 45 min");
  });

  it("pendiente sólo con horario", () => {
    expect(formatTaskMeta({ ...baseTask, duration_min: null })).toBe("14:00");
  });

  it("pendiente sólo con duración", () => {
    expect(formatTaskMeta({ ...baseTask, scheduled_at: null })).toBe("45 min");
  });

  it("pendiente sin horario ni duración → vacío", () => {
    expect(formatTaskMeta({ ...baseTask, scheduled_at: null, duration_min: null })).toBe("");
  });

  it("hecha con horario → 'HH:MM · completada'", () => {
    expect(formatTaskMeta({ ...baseTask, status: "done", scheduled_at: at(9, 15) })).toBe(
      "09:15 · completada",
    );
  });

  it("hecha sin horario → 'completada'", () => {
    expect(formatTaskMeta({ ...baseTask, status: "done", scheduled_at: null })).toBe("completada");
  });
});
