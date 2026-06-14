import { ONBOARDING_STEPS, STEP_INDEX } from "@ynara/core/features/onboarding";
import { useCallback } from "react";
import { useOnboardingStore } from "@/stores/onboarding";

/**
 * Navegación del wizard de onboarding (mobile). A diferencia de la web (que
 * usa rutas por step), acá el wizard es una sola pantalla manejada por
 * `currentStep` del draft store. `next`/`back` solo mueven ese step.
 */
export function useOnboardingNav() {
  const currentStep = useOnboardingStore((s) => s.currentStep);
  const setStep = useOnboardingStore((s) => s.setStep);

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
