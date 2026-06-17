import { describe, expect, it } from "vitest";
import { relativeTime } from "./relativeTime";

const NOW = 1_000_000_000_000;
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

describe("relativeTime", () => {
  it("muestra 'recién' bajo 1 minuto", () => {
    expect(relativeTime(NOW - 30_000, NOW)).toBe("recién");
  });

  it("minutos", () => {
    expect(relativeTime(NOW - 5 * MIN, NOW)).toBe("hace 5 min");
  });

  it("horas", () => {
    expect(relativeTime(NOW - 3 * HOUR, NOW)).toBe("hace 3 h");
  });

  it("'ayer' a 1 día exacto", () => {
    expect(relativeTime(NOW - DAY, NOW)).toBe("ayer");
  });

  it("días dentro de la semana", () => {
    expect(relativeTime(NOW - 3 * DAY, NOW)).toBe("hace 3 d");
  });

  it("semanas a partir de 7 días", () => {
    expect(relativeTime(NOW - 14 * DAY, NOW)).toBe("hace 2 sem");
  });

  it("clampa a 'recién' si el timestamp es futuro (clock skew)", () => {
    expect(relativeTime(NOW + 10 * MIN, NOW)).toBe("recién");
  });
});
