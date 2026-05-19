"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { type OnboardingStep, STEP_INDEX } from "@/features/onboarding/constants";
import { A11yStep } from "@/features/onboarding/steps/A11yStep";
import { AuthStep } from "@/features/onboarding/steps/AuthStep";
import { ModesStep } from "@/features/onboarding/steps/ModesStep";
import { MoodStep } from "@/features/onboarding/steps/MoodStep";
import { NameStep } from "@/features/onboarding/steps/NameStep";
import { useOnboardingStore } from "@/features/onboarding/store";

type Props = {
  step: OnboardingStep;
};

/**
 * Renderiza el step actual según el slug de la URL.
 *
 * Invariante "no podés saltar steps por URL manipulada":
 *   - URL > store → redirigir al currentStep real (bloqueo de adelanto).
 *   - URL < store → sincronizar store con URL (volver atrás es libre).
 *   - URL = store → no-op (evita race entre `setStep` y `router.push`
 *     durante `useOnboardingNav.next()`).
 */
export function StepRouter({ step }: Props) {
  const router = useRouter();
  const storeStep = useOnboardingStore((s) => s.currentStep);
  const setStep = useOnboardingStore((s) => s.setStep);

  useEffect(() => {
    const stepIndexFromUrl = STEP_INDEX[step];
    const storeStepIndex = STEP_INDEX[storeStep];
    if (stepIndexFromUrl > storeStepIndex) {
      router.replace(`/onboarding/${storeStep}`);
      return;
    }
    if (stepIndexFromUrl < storeStepIndex) {
      setStep(step);
    }
  }, [step, storeStep, router, setStep]);

  switch (step) {
    case "auth":
      return <AuthStep />;
    case "nombre":
      return <NameStep />;
    case "dia":
      return <MoodStep />;
    case "modos":
      return <ModesStep />;
    case "a11y":
      return <A11yStep />;
  }
}
