import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { OnboardingStep } from "./steps";

/**
 * Store del draft del onboarding, compartido web + mobile (ADR-012). Estado
 * provisional mientras el user avanza por los steps.
 *
 * El storage se inyecta: web pasa un storage efímero sobre `sessionStorage`
 * (si cierra el tab y vuelve, está OK perderlo; solo sobrevive el refresh
 * accidental); mobile pasa el suyo. Cuando completa, la app traslada estos
 * campos al user store y resetea este draft.
 */
export type OnboardingDraft = {
  /** Step actual; alimenta el dispatcher de la ruta del onboarding. */
  currentStep: OnboardingStep;

  // Step 1 — Auth
  authedUserId: string | null;
  authedToken: string | null;
  authMode: "signup" | "login" | null;

  // Step 2 — Nombre
  displayName: string;

  // Step 3 — Mood
  mood: string[];
  moodFreeText: string;

  // Step 4 — Modos
  interestedModes: string[];

  // Step 5 — A11y (mirror del a11y store para mostrar valores actuales en el
  // step; la fuente canónica de a11y es siempre el a11y store. Estos campos se
  // mantienen por compat pero no se leen al completar).
  a11yTextSize: "sm" | "md" | "lg";
  a11yHighContrast: boolean;
  a11yMotion: "auto" | "reduce" | "normal";
};

type OnboardingActions = {
  setStep: (step: OnboardingStep) => void;
  setAuth: (input: { userId: string; token: string; mode: "signup" | "login" }) => void;
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
 * Crea el store del draft de onboarding sobre el `storage` provisto. Cada app
 * lo instancia una vez (web con sessionStorage, mobile con el suyo).
 */
export function createOnboardingStore(storage: StateStorage) {
  return create<OnboardingDraft & OnboardingActions>()(
    persist(
      (set) => ({
        ...initialState,
        setStep: (currentStep) => set({ currentStep }),
        setAuth: ({ userId, token, mode }) =>
          set({ authedUserId: userId, authedToken: token, authMode: mode }),
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
        storage: createJSONStorage(() => storage),
      },
    ),
  );
}
