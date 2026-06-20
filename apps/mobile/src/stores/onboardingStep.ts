import { create } from "zustand";
import type { OnboardingStepId } from "@/features/onboarding/steps";

/**
 * Step actual del wizard de onboarding (mobile). Separado del draft store de core
 * porque la secuencia de pasos es mobile-only (incluye "sobre-vos"). Efímero (una
 * sesión): no se persiste; arranca en "auth" y se resetea al completar.
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
