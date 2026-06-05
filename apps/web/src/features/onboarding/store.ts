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

  // Step 3 — Mood
  mood: string[];
  moodFreeText: string;

  // Step 4 — Modos
  interestedModes: string[];

  // Step 5 — A11y (mirror del useA11yStore para mostrar valores actuales en
  // el step; la fuente canónica de a11y es siempre useA11yStore — D3 del
  // plan §7.4. Estos campos se mantienen por compat pero no se leen en
  // useCompleteOnboarding).
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
 * server-side `sessionStorage` no existe. Zustand v5 trata `undefined`
 * como "no persistir".
 *
 * El guard va FUERA de `createJSONStorage` porque algunas resoluciones
 * de tipos (con el lockfile actualizado) no aceptan factory que retorna
 * `Storage | undefined`. Devolver `undefined` directo es equivalente
 * semánticamente: persist() no escribe en server.
 */
const sessionJsonStorage =
  typeof window === "undefined" ? undefined : createJSONStorage(() => sessionStorage);

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
