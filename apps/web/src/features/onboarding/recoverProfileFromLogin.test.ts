import type { LoginResult } from "@ynara/core/features/auth";
import { beforeEach, describe, expect, it, vi } from "vitest";

// `applyA11yClasses` toca `document`/`matchMedia` (no fiable en jsdom): la
// mockeamos, pero dejamos el `useA11yStore` REAL para verificar que la
// hidratación escribe en el store. Partial mock vía importOriginal.
vi.mock("@/stores/a11y", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/stores/a11y")>();
  return { ...actual, applyA11yClasses: vi.fn() };
});

import { useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";
import { recoverProfileFromLogin } from "./recoverProfileFromLogin";

function makeSession(overrides: Partial<LoginResult["user"]> = {}): LoginResult {
  return {
    userId: "u1",
    token: "t1",
    user: {
      id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      email: "mateo@ynara.app",
      display_name: "Mateo",
      is_ephemeral: false,
      onboarding_completed: true,
      time_zone: "UTC",
      retention_sensitive_days: 365,
      preferences: {
        interested_modes: ["productividad", "estudio"],
        a11y: { text_size: "lg", high_contrast: true, motion: "reduce" },
      },
      created_at: "2025-01-01T00:00:00+00:00",
      updated_at: "2025-01-01T00:00:00+00:00",
      ...overrides,
    },
  };
}

beforeEach(() => {
  useUserStore.getState().reset();
  useA11yStore.getState().reset();
});

describe("recoverProfileFromLogin", () => {
  it("dispositivo nuevo: hidrata user store + a11y desde el me y marca onboarding", () => {
    recoverProfileFromLogin(makeSession());

    const u = useUserStore.getState();
    expect(u.userId).toBe("u1");
    expect(u.token).toBe("t1");
    expect(u.displayName).toBe("Mateo");
    expect(u.interestedModes).toEqual(["productividad", "estudio"]);
    expect(u.onboardingCompleted).toBe(true);

    const a = useA11yStore.getState();
    expect(a.textSize).toBe("lg");
    expect(a.highContrast).toBe(true);
    expect(a.motion).toBe("reduce");
  });

  it("no pisa una a11y local ya customizada (no-clobber)", () => {
    useA11yStore.getState().setTextSize("sm");

    recoverProfileFromLogin(makeSession());

    // Lo local estaba customizado (≠ default) → la a11y del server NO se adopta.
    expect(useA11yStore.getState().textSize).toBe("sm");
  });

  it("no falsea onboardedAt (queda null, no la fecha del login)", () => {
    recoverProfileFromLogin(makeSession());
    expect(useUserStore.getState().onboardedAt).toBeNull();
  });
});
