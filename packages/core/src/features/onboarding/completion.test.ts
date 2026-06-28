import { beforeEach, describe, expect, it, vi } from "vitest";

// Mockeamos el cliente HTTP de core: este módulo hace `POST /v1/onboarding`
// (intake completo, ADR-026) + un `PATCH /v1/users/me` best-effort para el huso.
// El test verifica el armado/mapeo del payload (camelCase→snake_case), el guard
// de auth y el carácter best-effort del PATCH; no la red.
const post = vi.fn();
const patch = vi.fn();
vi.mock("../../api", () => ({ api: { post, patch } }));

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

// "about" del draft base: sobre-vos en blanco (dedication null, free-text "").
const EMPTY_ABOUT = {
  dedication: null,
  study_what: "",
  work_what: "",
  purpose: "",
  interests: "",
};

beforeEach(() => {
  post.mockReset();
  patch.mockReset();
  post.mockResolvedValue({ id: "u1", onboarding_completed: true });
  patch.mockResolvedValue({ id: "u1" });
  // Huso determinístico: submitOnboarding captura el timeZone del browser en el
  // PATCH best-effort. Lo fijamos a Buenos Aires para aislar el assert del huso
  // real de la máquina/CI. Los casos que necesitan otro valor re-stubean el spy.
  vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
    timeZone: "America/Argentina/Buenos_Aires",
  } as Intl.ResolvedDateTimeFormatOptions);
});

describe("submitOnboarding", () => {
  it("happy: POST /v1/onboarding snake_case con Bearer + PATCH huso, devuelve el intake validado", async () => {
    const result = await submitOnboarding({ draft: makeDraft(), a11y });

    // Intake completo (ADR-026), camelCase→snake_case, con el Bearer del draft
    // (el cliente no adjunta el Bearer solo durante el onboarding). mood/about
    // viajan aunque el backend los descarte hasta G4.
    expect(post).toHaveBeenCalledWith(
      "/v1/onboarding",
      {
        display_name: "Mateo",
        interested_modes: ["productividad"],
        a11y: { text_size: "md", high_contrast: false, motion: "auto" },
        mood: ["tranquilo"],
        mood_free_text: null,
        about: EMPTY_ABOUT,
      },
      { headers: { Authorization: "Bearer t1" } },
    );
    // time_zone fuera del intake (ADR-026 §1): PATCH best-effort aparte, mismo Bearer.
    expect(patch).toHaveBeenCalledWith(
      "/v1/users/me",
      { time_zone: "America/Argentina/Buenos_Aires" },
      { headers: { Authorization: "Bearer t1" } },
    );
    expect(result).toMatchObject({
      displayName: "Mateo",
      interestedModes: ["productividad"],
      a11y: { textSize: "md", highContrast: false, motion: "auto" },
    });
  });

  it("mapea sobre-vos y mood_free_text al wire snake_case", async () => {
    const draft = makeDraft({
      mood: ["ansioso"],
      moodFreeText: "arrancando el dia",
      dedication: "ambos",
      studyWhat: "ingenieria",
      workWhat: "freelance",
      purpose: "organizarme",
      interests: "musica, running",
    });

    await submitOnboarding({ draft, a11y });

    expect(post).toHaveBeenCalledWith(
      "/v1/onboarding",
      expect.objectContaining({
        mood: ["ansioso"],
        mood_free_text: "arrancando el dia",
        about: {
          dedication: "ambos",
          study_what: "ingenieria",
          work_what: "freelance",
          purpose: "organizarme",
          interests: "musica, running",
        },
      }),
      { headers: { Authorization: "Bearer t1" } },
    );
  });

  it("huso indefinido: postea el intake pero NO patchea el huso", async () => {
    // El runtime no resuelve un timeZone → el PATCH best-effort ni se intenta.
    vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
      timeZone: undefined,
    } as unknown as Intl.ResolvedDateTimeFormatOptions);

    await submitOnboarding({ draft: makeDraft(), a11y });

    expect(post).toHaveBeenCalledTimes(1);
    expect(patch).not.toHaveBeenCalled();
  });

  it("el PATCH de huso es best-effort: si falla, NO rompe el cierre", async () => {
    // El POST cerró el onboarding; un fallo del PATCH de huso se traga.
    patch.mockRejectedValue(new Error("network"));

    const result = await submitOnboarding({ draft: makeDraft(), a11y });

    expect(post).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ displayName: "Mateo" });
  });

  it("el POST falla (camino crítico): propaga el throw y NO patchea el huso", async () => {
    // A diferencia del PATCH de huso, el POST NO es best-effort: si falla, el
    // onboarding no se cerró → el error sube al caller (que muestra el mensaje) y
    // no se intenta el PATCH del huso.
    post.mockRejectedValue(new Error("500"));

    await expect(submitOnboarding({ draft: makeDraft(), a11y })).rejects.toThrow();
    expect(patch).not.toHaveBeenCalled();
  });

  it("payload inválido (interestedModes vacío): throw y NO llama al backend", async () => {
    const draft = makeDraft({ interestedModes: [] });

    await expect(submitOnboarding({ draft, a11y })).rejects.toThrow();
    expect(post).not.toHaveBeenCalled();
    expect(patch).not.toHaveBeenCalled();
  });

  it("sin authedToken: throw 'Sesión inválida' y NO llama al backend", async () => {
    const draft = makeDraft({ authedToken: null });

    await expect(submitOnboarding({ draft, a11y })).rejects.toThrow(/sesión inválida/i);
    expect(post).not.toHaveBeenCalled();
    expect(patch).not.toHaveBeenCalled();
  });
});
