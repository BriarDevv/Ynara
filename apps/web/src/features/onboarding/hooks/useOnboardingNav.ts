"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { ONBOARDING_STEPS, type OnboardingStep, STEP_INDEX } from "../constants";
import { useOnboardingStore } from "../store";

/**
 * API de navegación del onboarding.
 *
 * - `currentStep` lee desde el store (sessionStorage), no desde la URL.
 *   Si hay mismatch (URL vs store), el dispatcher fuerza al usuario al
 *   step real del store (no se permite saltar steps por URL manipulada).
 * - `next()` y `back()` actualizan store + URL juntos.
 * - `goTo()` para volver a un step previo (link "editar" en un resumen).
 */
export function useOnboardingNav(currentFromUrl: OnboardingStep) {
  const router = useRouter();
  const storeStep = useOnboardingStore((s) => s.currentStep);
  const setStep = useOnboardingStore((s) => s.setStep);

  const index = STEP_INDEX[currentFromUrl];
  const isFirst = index === 0;
  const isLast = index === ONBOARDING_STEPS.length - 1;

  const next = useCallback(() => {
    if (isLast) return;
    const nextSlug = ONBOARDING_STEPS[index + 1];
    if (!nextSlug) return;
    setStep(nextSlug);
    router.push(`/onboarding/${nextSlug}`);
  }, [index, isLast, router, setStep]);

  const back = useCallback(() => {
    if (isFirst) return;
    const prevSlug = ONBOARDING_STEPS[index - 1];
    if (!prevSlug) return;
    setStep(prevSlug);
    router.push(`/onboarding/${prevSlug}`);
  }, [index, isFirst, router, setStep]);

  const goTo = useCallback(
    (slug: OnboardingStep) => {
      setStep(slug);
      router.push(`/onboarding/${slug}`);
    },
    [router, setStep],
  );

  return {
    currentStep: currentFromUrl,
    storeStep,
    index,
    total: ONBOARDING_STEPS.length,
    isFirst,
    isLast,
    next,
    back,
    goTo,
  };
}
