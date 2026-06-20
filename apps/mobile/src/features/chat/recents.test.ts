import type { ChatSessionMeta, ChatUiMessage } from "@ynara/core/features/chat";
import { describe, expect, it } from "vitest";
import { buildRecents, inTimeBucket, matchesQuery, sessionName, UNNAMED } from "./recents";

const msg = (role: string, text: string): ChatUiMessage => ({
  id: Math.random().toString(),
  role: role as never,
  text,
  status: "done",
});

const sess = (id: string, mode: string, updatedAt: number): ChatSessionMeta => ({
  id,
  mode: mode as never,
  createdAt: updatedAt,
  updatedAt,
});

describe("sessionName", () => {
  it("toma la primera línea del primer mensaje del usuario", () => {
    expect(sessionName([msg("user", "Hola, ¿cómo estás?")])).toBe("Hola, ¿cómo estás?");
  });
  it("ignora mensajes del assistant previos", () => {
    expect(sessionName([msg("assistant", "Bienvenido"), msg("user", "Necesito ayuda")])).toBe(
      "Necesito ayuda",
    );
  });
  it("se queda solo con la primera línea", () => {
    expect(sessionName([msg("user", "Comprar leche\ny pan\ny huevos")])).toBe("Comprar leche");
  });
  it("recorta nombres largos con elipsis", () => {
    const long = "a".repeat(60);
    const name = sessionName([msg("user", long)]);
    expect(name.endsWith("…")).toBe(true);
    expect(name.length).toBeLessThanOrEqual(41);
  });
  it("UNNAMED si no hay mensaje de usuario", () => {
    expect(sessionName([msg("assistant", "Hola")])).toBe(UNNAMED);
    expect(sessionName([])).toBe(UNNAMED);
    expect(sessionName(undefined)).toBe(UNNAMED);
  });
  it("saltea mensajes de usuario en blanco", () => {
    expect(sessionName([msg("user", "   "), msg("user", "Real")])).toBe("Real");
  });
});

describe("inTimeBucket", () => {
  const now = new Date(2026, 5, 20, 15, 0, 0).getTime();
  const todayMorning = new Date(2026, 5, 20, 8, 0, 0).getTime();
  const yesterdayNight = new Date(2026, 5, 19, 22, 0, 0).getTime();
  const fiveDaysAgo = new Date(2026, 5, 15, 12, 0, 0).getTime();
  const lastMonth = new Date(2026, 4, 25, 12, 0, 0).getTime();
  const longAgo = new Date(2026, 2, 1, 12, 0, 0).getTime();

  it("todos siempre true", () => {
    expect(inTimeBucket(longAgo, now, "todos")).toBe(true);
  });
  it("hoy: solo el día calendario actual", () => {
    expect(inTimeBucket(todayMorning, now, "hoy")).toBe(true);
    expect(inTimeBucket(yesterdayNight, now, "hoy")).toBe(false);
  });
  it("ayer: solo el día anterior", () => {
    expect(inTimeBucket(yesterdayNight, now, "ayer")).toBe(true);
    expect(inTimeBucket(todayMorning, now, "ayer")).toBe(false);
    expect(inTimeBucket(fiveDaysAgo, now, "ayer")).toBe(false);
  });
  it("semana: últimos 7 días", () => {
    expect(inTimeBucket(fiveDaysAgo, now, "semana")).toBe(true);
    expect(inTimeBucket(lastMonth, now, "semana")).toBe(false);
  });
  it("mes: últimos 30 días", () => {
    expect(inTimeBucket(lastMonth, now, "mes")).toBe(true);
    expect(inTimeBucket(longAgo, now, "mes")).toBe(false);
  });
});

describe("matchesQuery", () => {
  it("query vacío matchea todo", () => {
    expect(matchesQuery("lo que sea", "")).toBe(true);
    expect(matchesQuery("lo que sea", "   ")).toBe(true);
  });
  it("es insensible a mayúsculas", () => {
    expect(matchesQuery("Comprar Leche", "leche")).toBe(true);
  });
  it("es insensible a acentos", () => {
    expect(matchesQuery("Plan de acción", "accion")).toBe(true);
  });
  it("no matchea lo que no está", () => {
    expect(matchesQuery("Comprar leche", "pan")).toBe(false);
  });
});

describe("buildRecents", () => {
  const now = new Date(2026, 5, 20, 15, 0, 0).getTime();
  const t1 = new Date(2026, 5, 20, 9, 0, 0).getTime();
  const t2 = new Date(2026, 5, 20, 12, 0, 0).getTime();
  const old = new Date(2026, 2, 1, 12, 0, 0).getTime();
  const sessions = {
    a: sess("a", "productividad", t1),
    b: sess("b", "vida", t2),
    c: sess("c", "estudio", old),
  };
  const messages = {
    a: [msg("user", "Organizar la semana")],
    b: [msg("user", "Receta de tarta")],
    c: [msg("user", "Repaso de historia")],
  };

  it("ordena por updatedAt desc", () => {
    const out = buildRecents(sessions, messages, { query: "", bucket: "todos", now });
    expect(out.map((r) => r.id)).toEqual(["b", "a", "c"]);
  });
  it("filtra por bucket temporal", () => {
    const out = buildRecents(sessions, messages, { query: "", bucket: "hoy", now });
    expect(out.map((r) => r.id)).toEqual(["b", "a"]);
  });
  it("filtra por query sobre el auto-nombre", () => {
    const out = buildRecents(sessions, messages, { query: "receta", bucket: "todos", now });
    expect(out.map((r) => r.id)).toEqual(["b"]);
  });
  it("expone el auto-nombre derivado", () => {
    const out = buildRecents(sessions, messages, { query: "", bucket: "todos", now });
    expect(out.find((r) => r.id === "a")?.name).toBe("Organizar la semana");
  });
});
