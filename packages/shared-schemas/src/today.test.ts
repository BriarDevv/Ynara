import { describe, expect, it } from "vitest";

import {
  RecapSchema,
  SuggestionSchema,
  TaskPatchSchema,
  TaskSchema,
  TasksResponseSchema,
} from "./today";

const ISO = "2026-05-07T14:00:00+00:00";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const task = {
  id: UUID,
  title: "Llamada con equipo de diseño",
  status: "pending" as const,
  scheduled_at: ISO,
  duration_min: 45,
};

describe("TaskSchema", () => {
  it("acepta una tarea completa", () => {
    expect(TaskSchema.parse(task)).toEqual(task);
  });

  it("permite horario y duración nulos (tarea sin agenda)", () => {
    const parsed = TaskSchema.parse({ ...task, scheduled_at: null, duration_min: null });
    expect(parsed.scheduled_at).toBeNull();
    expect(parsed.duration_min).toBeNull();
  });

  it("rechaza título vacío", () => {
    expect(() => TaskSchema.parse({ ...task, title: "" })).toThrow();
  });

  it("rechaza estado fuera del enum", () => {
    expect(() => TaskSchema.parse({ ...task, status: "archived" })).toThrow();
  });

  it("rechaza duración no positiva", () => {
    expect(() => TaskSchema.parse({ ...task, duration_min: 0 })).toThrow();
  });
});

describe("TasksResponseSchema", () => {
  it("parsea items + total", () => {
    const parsed = TasksResponseSchema.parse({ items: [task], total: 1 });
    expect(parsed.items).toHaveLength(1);
    expect(parsed.total).toBe(1);
  });

  it("rechaza total negativo", () => {
    expect(() => TasksResponseSchema.parse({ items: [], total: -1 })).toThrow();
  });
});

describe("TaskPatchSchema", () => {
  it("acepta el toggle de estado", () => {
    expect(TaskPatchSchema.parse({ status: "done" })).toEqual({ status: "done" });
  });

  it("rechaza un body sin estado válido", () => {
    expect(() => TaskPatchSchema.parse({})).toThrow();
  });
});

describe("SuggestionSchema", () => {
  it("acepta una sugerencia con modo", () => {
    const suggestion = {
      id: UUID,
      title: "Bloque de foco 10:30–12:00",
      why: "90 min sin notificaciones para la propuesta Õmi",
      mode: "productividad" as const,
    };
    expect(SuggestionSchema.parse(suggestion)).toEqual(suggestion);
  });

  it("permite modo nulo (sugerencia transversal)", () => {
    const parsed = SuggestionSchema.parse({
      id: UUID,
      title: "Pausá 10 min · estirá",
      why: "Llevás 90 min en pantalla",
      mode: null,
    });
    expect(parsed.mode).toBeNull();
  });

  it("rechaza un porqué vacío", () => {
    expect(() => SuggestionSchema.parse({ id: UUID, title: "x", why: "", mode: null })).toThrow();
  });
});

describe("RecapSchema", () => {
  it("acepta un recap pendiente (sin headline)", () => {
    const parsed = RecapSchema.parse({
      pending: true,
      date: ISO,
      headline: null,
      highlights: [],
    });
    expect(parsed.pending).toBe(true);
    expect(parsed.highlights).toEqual([]);
  });

  it("acepta un recap cerrado con highlights", () => {
    const parsed = RecapSchema.parse({
      pending: false,
      date: ISO,
      headline: "Un día de foco profundo.",
      highlights: ["Cerraste el brief de Õmi", "90 min de foco sin cortes"],
    });
    expect(parsed.headline).toContain("foco");
    expect(parsed.highlights).toHaveLength(2);
  });
});
