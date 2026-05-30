import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { OnboardingStep } from "./constants";

/**
 * Estado provisional del onboarding mientras el user avanza por los steps.
 *
 * Persistido en `sessionStorage` (no localStorage): si el user cierra el
 * tab y vuelve, está OK perderlo; lo único que tiene que sobrevivir es
 * el refresh accidental.
 *
 * Cuando completa, useCompleteOnboarding traslada estos campos al
 * `useUserStore` (que vive en localStorage) y resetea este.
 */
export type OnboardingDraft = {
  /** Step actual; alimenta el dispatcher de /onboarding/[step]. */
  currentStep: OnboardingStep;

  // Step 1 — Auth
  authedUserId: string | null;
  authedToken: string | null;
  authMode: "signup" | "login" | "ephemeral" | null;

  // Step 2 — Nombre
  displayName: string;

  // Step 3 — Mood (Sesión 4)
  mood: string[];
  moodFreeText: string;

  // Step 4 — Modos (Sesión 4)
  interestedModes: string[];

  // Step 5 — A11y (Sesión 4)
  a11yTextSize: "sm" | "md" | "lg";
  a11yHighContrast: boolean;
  a11yMotion: "auto" | "reduce" | "normal";
};

type OnboardingActions = {
  setStep: (step: OnboardingStep) => void;
  setAuth: (input: {
    userId: string;
    token: string;
    mode: "signup" | "login" | "ephemeral";
  }) => void;
  /**
   * Resetea el draft y deja el user marcado como ephemeral en una
   * sola pasada. Evita la race teórica de llamar reset() + setAuth().
   */
  startEphemeral: (input: { userId: string; token: string }) => void;
  setDisplayName: (name: string) => void;
  setMood: (mood: string[], freeText: string) => void;
  setInterestedModes: (modes: string[]) => void;
  setA11y: (
    prefs: Partial<{
      textSize: OnboardingDraft["a11yTextSize"];
      highContrast: boolean;
      motion: OnboardingDraft["a11yMotion"];
    }>,
  ) => void;
  reset: () => void;
};

const initialState: OnboardingDraft = {
  currentStep: "auth",
  authedUserId: null,
  authedToken: null,
  authMode: null,
  displayName: "",
  mood: [],
  moodFreeText: "",
  interestedModes: [],
  a11yTextSize: "md",
  a11yHighContrast: false,
  a11yMotion: "auto",
};

/**
 * createJSONStorage(() => sessionStorage) con guard para SSR: en
 * server-side `sessionStorage` no existe. La factory de zustand 5.0.13
 * tipa el retorno como `StateStorage` (no acepta `undefined`), así que
 * devolvemos un storage no-op en server en vez de `undefined`.
 */
const noopStorage: StateStorage = {
  getItem: () => null,
  removeItem: () => undefined,
  setItem: () => undefined,
};

const sessionJsonStorage = createJSONStorage(() =>
  typeof window === "undefined" ? noopStorage : sessionStorage,
);

export const useOnboardingStore = create<OnboardingDraft & OnboardingActions>()(
  persist(
    (set) => ({
      ...initialState,
      setStep: (currentStep) => set({ currentStep }),
      setAuth: ({ userId, token, mode }) =>
        set({ authedUserId: userId, authedToken: token, authMode: mode }),
      startEphemeral: ({ userId, token }) =>
        set({
          ...initialState,
          authedUserId: userId,
          authedToken: token,
          authMode: "ephemeral",
        }),
      setDisplayName: (displayName) => set({ displayName }),
      setMood: (mood, moodFreeText) => set({ mood, moodFreeText }),
      setInterestedModes: (interestedModes) => set({ interestedModes }),
      setA11y: (prefs) =>
        set((s) => ({
          a11yTextSize: prefs.textSize ?? s.a11yTextSize,
          a11yHighContrast: prefs.highContrast ?? s.a11yHighContrast,
          a11yMotion: prefs.motion ?? s.a11yMotion,
        })),
      reset: () => set(initialState),
    }),
    {
      name: "ynara.onboarding",
      storage: sessionJsonStorage,
    },
  ),
);
