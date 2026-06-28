import type { UserOut } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import {
  deriveProfileHydration,
  type LocalA11ySnapshot,
  type LocalProfileSnapshot,
} from "./hydrate";

// Snapshots base: dispositivo nuevo (user vacío, a11y en el default).
const EMPTY_LOCAL: LocalProfileSnapshot = {
  displayName: "",
  interestedModes: [],
  onboardingCompleted: false,
};
const DEFAULT_A11Y: LocalA11ySnapshot = { textSize: "md", highContrast: false, motion: "auto" };

function makeMe(overrides: Partial<UserOut> = {}): UserOut {
  return {
    id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    email: "mateo@ynara.app",
    display_name: "Mateo",
    onboarding_completed: true,
    retention_sensitive_days: 365,
    preferences: {
      interested_modes: ["productividad", "estudio"],
      a11y: { text_size: "lg", high_contrast: true, motion: "reduce" },
    },
    created_at: "2025-01-01T00:00:00+00:00",
    updated_at: "2025-01-01T00:00:00+00:00",
    ...overrides,
  };
}

describe("deriveProfileHydration", () => {
  it("dispositivo nuevo: adopta nombre + modos + onboarding + a11y del backend", () => {
    const h = deriveProfileHydration({ local: EMPTY_LOCAL, localA11y: DEFAULT_A11Y, me: makeMe() });
    expect(h.user).toEqual({
      displayName: "Mateo",
      interestedModes: ["productividad", "estudio"],
      onboardingCompleted: true,
    });
    expect(h.a11y).toEqual({ textSize: "lg", highContrast: true, motion: "reduce" });
  });

  it("no pisa el displayName local si ya hay uno", () => {
    const h = deriveProfileHydration({
      local: { ...EMPTY_LOCAL, displayName: "Local" },
      localA11y: DEFAULT_A11Y,
      me: makeMe(),
    });
    expect(h.user.displayName).toBeUndefined();
  });

  it("no pisa los modos locales si ya hay alguno", () => {
    const h = deriveProfileHydration({
      local: { ...EMPTY_LOCAL, interestedModes: ["vida"] },
      localA11y: DEFAULT_A11Y,
      me: makeMe(),
    });
    expect(h.user.interestedModes).toBeUndefined();
  });

  it("NO adopta a11y del server si lo local ya está customizado", () => {
    const h = deriveProfileHydration({
      local: EMPTY_LOCAL,
      localA11y: { textSize: "sm", highContrast: false, motion: "auto" },
      me: makeMe(),
    });
    expect(h.a11y).toEqual({});
  });

  it("preferences vacío (fila pre-onboarding): no adopta modos ni a11y", () => {
    const h = deriveProfileHydration({
      local: EMPTY_LOCAL,
      localA11y: DEFAULT_A11Y,
      me: makeMe({ preferences: {} }),
    });
    expect(h.user.interestedModes).toBeUndefined();
    expect(h.a11y).toEqual({});
  });

  it("no marca onboardingCompleted si el server dice false", () => {
    const h = deriveProfileHydration({
      local: EMPTY_LOCAL,
      localA11y: DEFAULT_A11Y,
      me: makeMe({ onboarding_completed: false }),
    });
    expect(h.user.onboardingCompleted).toBeUndefined();
  });

  it("display_name null en el server: no rellena nombre", () => {
    const h = deriveProfileHydration({
      local: EMPTY_LOCAL,
      localA11y: DEFAULT_A11Y,
      me: makeMe({ display_name: null }),
    });
    expect(h.user.displayName).toBeUndefined();
  });
});
