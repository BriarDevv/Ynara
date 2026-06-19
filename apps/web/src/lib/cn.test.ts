import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  // El footgun que motivó extender tailwind-merge: las utilities tipográficas
  // custom (text-display/title/subtitle/...) se descartaban al combinarlas con
  // un color arbitrario (ink token) dentro del mismo cn, dejando el texto en el
  // font-size default.
  it("conserva la utility tipográfica custom junto al color arbitrario (mismo arg)", () => {
    const result = cn("text-subtitle text-[var(--color-ink)]");
    expect(result).toContain("text-subtitle");
    expect(result).toContain("text-[var(--color-ink)]");
  });

  it("conserva text-display + color en args separados (caso del hero)", () => {
    const result = cn("text-display", "text-[var(--color-ink-deep)]");
    expect(result).toContain("text-display");
    expect(result).toContain("text-[var(--color-ink-deep)]");
  });

  it("entre dos tipografías custom gana la última (siguen en conflicto)", () => {
    const result = cn("text-title", "text-display");
    expect(result).toContain("text-display");
    expect(result).not.toContain("text-title");
  });

  it("sigue dedupeando los font-sizes nativos de Tailwind", () => {
    expect(cn("text-sm", "text-lg")).toBe("text-lg");
  });

  it("sigue dedupeando colores arbitrarios entre sí (gana el último)", () => {
    expect(cn("text-[var(--color-ink-soft)]", "text-[var(--color-ink)]")).toBe(
      "text-[var(--color-ink)]",
    );
  });
});
