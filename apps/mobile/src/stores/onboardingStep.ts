import { create } from "zustand";
import type { OnboardingStepId } from "@/features/onboarding/steps";

/**
 * Step ACTUAL del wizard de onboarding (mobile): puro UI state de qué pantalla se
 * muestra. El ORDEN de los pasos vive en @ynara/core (compartido con web); acá
 * solo guardamos en cuál estamos. Efímero (una sesión): no se persiste; arranca
 * en "auth" y se resetea al completar.
 */
export const useOnboardingStepStore = create<{
  step: OnboardingStepId;
  setStep: (step: OnboardingStepId) => void;
  reset: () => void;
}>((set) => ({
  step: "auth",
  setStep: (step) => set({ step }),
  reset: () => set({ step: "auth" }),
}));
