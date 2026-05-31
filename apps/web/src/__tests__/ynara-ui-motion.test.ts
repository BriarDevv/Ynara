// Presets de motion de @ynara/ui (DESIGN.md §8). Espejan los tokens de
// globals.css; este test los ancla y de paso ejercita el wiring.
import { DURATION, EASE_OUT_SOFT, SPRING_SNAPPY, SPRING_SOFT } from "@ynara/ui";
import { describe, expect, it } from "vitest";

describe("@ynara/ui · presets de motion", () => {
  it("springs según el modelo perceptual de §8.1", () => {
    expect(SPRING_SNAPPY).toEqual({ visualDuration: 0.2, bounce: 0 });
    expect(SPRING_SOFT).toEqual({ visualDuration: 0.35, bounce: 0.15 });
  });

  it("duraciones espejan los tokens --duration-* (ms)", () => {
    expect(DURATION).toEqual({ instant: 100, fast: 150, base: 200, slow: 300, screen: 350 });
  });

  it("easing espeja --ease-out-soft", () => {
    expect(EASE_OUT_SOFT).toEqual([0.22, 1, 0.36, 1]);
  });
});
