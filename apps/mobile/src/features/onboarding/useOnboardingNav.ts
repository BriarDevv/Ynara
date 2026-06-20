import { useCallback } from "react";
import { useOnboardingStepStore } from "@/stores/onboardingStep";
import { ONBOARDING_STEPS, STEP_INDEX } from "./steps";

/**
 * Navegación del wizard de onboarding (mobile). El wizard es una sola pantalla
 * manejada por `step` del step store (mobile, decoplado de core para incluir
 * "sobre-vos"). `next`/`back` solo mueven ese step.
 */
export function useOnboardingNav() {
  const currentStep = useOnboardingStepStore((s) => s.step);
  const setStep = useOnboardingStepStore((s) => s.setStep);

  const index = STEP_INDEX[currentStep];
  const isFirst = index === 0;
  const isLast = index === ONBOARDING_STEPS.length - 1;

  const next = useCallback(() => {
    const nextSlug = ONBOARDING_STEPS[index + 1];
    if (nextSlug) setStep(nextSlug);
  }, [index, setStep]);

  const back = useCallback(() => {
    const prevSlug = ONBOARDING_STEPS[index - 1];
    if (prevSlug) setStep(prevSlug);
  }, [index, setStep]);

  return {
    currentStep,
    index,
    total: ONBOARDING_STEPS.length,
    isFirst,
    isLast,
    next,
    back,
  };
}
