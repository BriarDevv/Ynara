import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
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

  // Step 5 — A11y: las preferencias visuales viven en `useA11yStore`
  // (localStorage + clases en <html>), no en el draft. No se duplican acá.
};

type OnboardingActions = {
  setStep: (step: OnboardingStep) => void;
  setAuth: (input: {
    userId: string;
    token: string;
    mode: "signup" | "login" | "ephemeral";
  }) => void;
  setDisplayName: (name: string) => void;
  setMood: (mood: string[], freeText: string) => void;
  setInterestedModes: (modes: string[]) => void;
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
};

/**
 * createJSONStorage(() => sessionStorage) con guard para SSR: en
 * server-side `sessionStorage` no existe; devolvemos un storage no-op
 * y Zustand resuelve fallback.
 */
const noopStorage: Storage = {
  length: 0,
  clear: () => undefined,
  getItem: () => null,
  key: () => null,
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
      setDisplayName: (displayName) => set({ displayName }),
      setMood: (mood, moodFreeText) => set({ mood, moodFreeText }),
      setInterestedModes: (interestedModes) => set({ interestedModes }),
      reset: () => set(initialState),
    }),
    {
      name: "ynara.onboarding",
      storage: sessionJsonStorage,
    },
  ),
);
