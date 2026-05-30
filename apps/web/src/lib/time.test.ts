import { describe, expect, it } from "vitest";
import { getGreeting } from "./time";

/**
 * `getGreeting` es pura: recibe la fecha por parámetro. Construimos Dates
 * locales (el código usa `getHours()`, hora local) en horas fijas para
 * cubrir los 3 rangos y sus bordes (plan §5.2).
 */
function at(hour: number, minute = 0): Date {
  return new Date(2026, 4, 30, hour, minute, 0, 0);
}

describe("getGreeting", () => {
  it('returns "Buen día" durante la mañana (06:00–11:59)', () => {
    expect(getGreeting(at(6, 0))).toBe("Buen día");
    expect(getGreeting(at(9, 30))).toBe("Buen día");
    expect(getGreeting(at(11, 59))).toBe("Buen día");
  });

  it('returns "Buenas tardes" durante la tarde (12:00–19:59)', () => {
    expect(getGreeting(at(12, 0))).toBe("Buenas tardes");
    expect(getGreeting(at(15, 0))).toBe("Buenas tardes");
    expect(getGreeting(at(19, 59))).toBe("Buenas tardes");
  });

  it('returns "Buenas noches" durante la noche (20:00–05:59)', () => {
    expect(getGreeting(at(20, 0))).toBe("Buenas noches");
    expect(getGreeting(at(23, 59))).toBe("Buenas noches");
    expect(getGreeting(at(0, 0))).toBe("Buenas noches");
    expect(getGreeting(at(5, 59))).toBe("Buenas noches");
  });

  it("trata 05:59 como noche y 06:00 como mañana (borde inferior)", () => {
    expect(getGreeting(at(5, 59))).toBe("Buenas noches");
    expect(getGreeting(at(6, 0))).toBe("Buen día");
  });

  it("trata 11:59 como mañana y 12:00 como tarde (borde mediodía)", () => {
    expect(getGreeting(at(11, 59))).toBe("Buen día");
    expect(getGreeting(at(12, 0))).toBe("Buenas tardes");
  });

  it("trata 19:59 como tarde y 20:00 como noche (borde superior)", () => {
    expect(getGreeting(at(19, 59))).toBe("Buenas tardes");
    expect(getGreeting(at(20, 0))).toBe("Buenas noches");
  });
});
