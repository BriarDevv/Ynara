import { describe, expect, it } from "vitest";
import { mostRecentSessionOfMode, RESUME_TIMEOUT_MS, shouldResume } from "./session";

const s = (id: string, mode: string, updatedAt: number) => ({ id, mode: mode as never, updatedAt });

describe("shouldResume", () => {
  it("false sin sesión activa", () => {
    expect(shouldResume(null, 1000, 1000)).toBe(false);
  });
  it("false si lastActiveAt es null", () => {
    expect(shouldResume("a", null, 1000)).toBe(false);
  });
  it("true si volviste dentro del umbral", () => {
    expect(shouldResume("a", 1000, 1000 + RESUME_TIMEOUT_MS - 1)).toBe(true);
  });
  it("false si pasó el umbral", () => {
    expect(shouldResume("a", 1000, 1000 + RESUME_TIMEOUT_MS)).toBe(false);
    expect(shouldResume("a", 1000, 1000 + RESUME_TIMEOUT_MS + 1)).toBe(false);
  });
});

describe("mostRecentSessionOfMode", () => {
  const sessions = {
    a: s("a", "vida", 100),
    b: s("b", "vida", 300),
    c: s("c", "estudio", 200),
  };
  it("devuelve la más reciente del modo", () => {
    expect(mostRecentSessionOfMode(sessions, "vida" as never)?.id).toBe("b");
  });
  it("ignora otros modos", () => {
    expect(mostRecentSessionOfMode(sessions, "estudio" as never)?.id).toBe("c");
  });
  it("undefined si no hay del modo", () => {
    expect(mostRecentSessionOfMode(sessions, "memoria" as never)).toBeUndefined();
  });
});
