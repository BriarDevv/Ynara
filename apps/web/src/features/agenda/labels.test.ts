import { describe, expect, it } from "vitest";
import {
  formatDayLong,
  formatDayNum,
  formatWeekdayShort,
  formatWeekRange,
  isSameDay,
} from "./labels";

/**
 * Aserciones tolerantes a la versión de ICU: chequean estructura (capitalización,
 * número de día, nombres de mes, guion) y no strings exactos, para no romperse
 * si el formato es-AR de Intl cambia de minor.
 */

describe("formatDayLong", () => {
  it("capitaliza la inicial e incluye el número de día", () => {
    const s = formatDayLong(new Date(2026, 4, 7)); // 7 de mayo
    expect(s.charAt(0)).toBe(s.charAt(0).toUpperCase());
    expect(s).toContain("7");
  });
});

describe("formatWeekdayShort", () => {
  it("devuelve un día corto capitalizado y sin punto final", () => {
    const s = formatWeekdayShort(new Date(2026, 4, 7));
    expect(s.length).toBeGreaterThan(0);
    expect(s).not.toMatch(/\.$/);
    expect(s.charAt(0)).toBe(s.charAt(0).toUpperCase());
  });
});

describe("formatDayNum", () => {
  it("devuelve el número de día", () => {
    expect(formatDayNum(new Date(2026, 4, 7))).toBe("7");
  });
});

describe("formatWeekRange", () => {
  it("semana en un mismo mes: un solo nombre de mes y guion", () => {
    const s = formatWeekRange(new Date(2026, 4, 4)); // → domingo 10 de mayo
    expect(s).toContain("–");
    expect(s).toContain("4");
    expect(s).toContain("10");
    expect(s.match(/mayo/g)?.length).toBe(1);
  });

  it("semana que cruza de mes: dos nombres de mes", () => {
    const s = formatWeekRange(new Date(2026, 3, 27)); // → domingo 3 de mayo
    expect(s).toContain("–");
    expect(s).toContain("abril");
    expect(s).toContain("mayo");
  });
});

describe("isSameDay", () => {
  it("true para el mismo día con distinta hora", () => {
    expect(isSameDay(new Date(2026, 4, 7, 8, 0), new Date(2026, 4, 7, 23, 0))).toBe(true);
  });

  it("false para días distintos", () => {
    expect(isSameDay(new Date(2026, 4, 7), new Date(2026, 4, 8))).toBe(false);
  });
});
