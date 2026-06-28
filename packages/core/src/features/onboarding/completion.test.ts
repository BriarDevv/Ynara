import { beforeEach, describe, expect, it, vi } from "vitest";

// Mockeamos el cliente HTTP de core: este módulo hace `PATCH /v1/users/me`
// (no existe `/v1/user/onboard` en el backend real). El test verifica el
// armado/validación del payload y el guard de auth, no la red.
const patch = vi.fn();
vi.mock("../../api", () => ({ api: { patch } }));

const { submitOnboarding } = await import("./completion");
const { createOnboardingStore } = await import("./store");

import type { OnboardingA11yPrefs } from "./completion";
import type { OnboardingDraft } from "./store";

// Storage en memoria para instanciar el draft store sin tocar plataforma.
function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => {
      map.set(k, v);
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
  };
}

// Draft válido base; cada test ajusta lo que necesita. Tomamos el estado del
// store real (mismo shape canónico que usan web/mobile) para no driftear.
function makeDraft(overrides: Partial<OnboardingDraft> = {}): OnboardingDraft {
  const store = createOnboardingStore(memoryStorage());
  store.getState().setDisplayName("Mateo");
  store.getState().setMood(["tranquilo"], "");
  store.getState().setInterestedModes(["productividad"]);
  store.getState().setAuth({ userId: "u1", token: "t1", mode: "signup" });
  return { ...store.getState(), ...overrides };
}

const a11y: OnboardingA11yPrefs = { textSize: "md", highContrast: false, motion: "auto" };

beforeEach(() => {
  patch.mockReset();
});

describe("submitOnboarding", () => {
  it("happy: PATCH /v1/users/me snake_case con Bearer y devuelve el payload validado", async () => {
    patch.mockResolvedValue({ id: "u1", onboarding_completed: true });

    const result = await submitOnboarding({ draft: makeDraft(), a11y });

    // Contrato real: SOLO los campos que `UserUpdate` acepta (snake_case,
    // extra='forbid'); mood/interestedModes/a11y NO viajan al backend. El token
    // del draft viaja EXPLÍCITO (el cliente no adjunta el Bearer durante el onboarding).
    expect(patch).toHaveBeenCalledWith(
      "/v1/users/me",
      { display_name: "Mateo", onboarding_completed: true },
      { headers: { Authorization: "Bearer t1" } },
    );
    expect(result).toMatchObject({
      displayName: "Mateo",
      interestedModes: ["productividad"],
      a11y: { textSize: "md", highContrast: false, motion: "auto" },
    });
  });

  it("payload inválido (interestedModes vacío): throw y NO llama al backend", async () => {
    const draft = makeDraft({ interestedModes: [] });

    await expect(submitOnboarding({ draft, a11y })).rejects.toThrow();
    expect(patch).not.toHaveBeenCalled();
  });

  it("sin authedToken: throw 'Sesión inválida' y NO llama al backend", async () => {
    const draft = makeDraft({ authedToken: null });

    await expect(submitOnboarding({ draft, a11y })).rejects.toThrow(/sesión inválida/i);
    expect(patch).not.toHaveBeenCalled();
  });
});
