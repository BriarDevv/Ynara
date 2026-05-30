"use client";

import { useEffect } from "react";
import type { OnboardingStep } from "@/features/onboarding/constants";
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
 * También sincroniza el store: si alguien navega directo a una URL
 * (e.g. /onboarding/modos) que el store dice que no le toca todavía,
 * por ahora dejamos pasar y actualizamos el store. La invariante
 * "no podés saltar steps por URL manipulada" queda como hardening
 * pendiente (ver TODO abajo).
 */
export function StepRouter({ step }: Props) {
  const setStep = useOnboardingStore((s) => s.setStep);

  useEffect(() => {
    setStep(step);
  }, [step, setStep]);

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
