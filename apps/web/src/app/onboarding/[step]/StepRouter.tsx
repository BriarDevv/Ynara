"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
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
 *   - URL = store → no-op.
 *
 * **Importante** — el effect depende SOLO de `step` (URL slug), no de
 * `storeStep`. Esto evita la race que se manifestaba al hacer
 * `setStep(next) + router.push(next)` desde un handler: el store cambiaba
 * ANTES de que la URL refrescara, este effect se re-disparaba con la
 * URL vieja y volvía a llamar `setStep(URL=viejo)`, deshaciendo el
 * avance. Leemos `currentStep` con `getState()` (no reactivo) sólo en
 * el momento de comparar, y guardamos en un ref la última URL ya
 * procesada para no re-ejecutar el guard si nada navegó.
 */
export function StepRouter({ step }: Props) {
  const router = useRouter();
  const lastProcessedStep = useRef<OnboardingStep | null>(null);

  // El effect reacciona al slug de la URL (`step`, un route segment), no a un
  // evento de UI: el disparador es la navegación de ruta, no hay handler donde
  // mover esta lógica de guard.
  useEffect(() => {
    if (lastProcessedStep.current === step) return;
    lastProcessedStep.current = step;

    const storeStep = useOnboardingStore.getState().currentStep;
    // react-doctor-disable-next-line react-doctor/no-event-handler
    const stepIndexFromUrl = STEP_INDEX[step];
    const storeStepIndex = STEP_INDEX[storeStep];

    if (stepIndexFromUrl > storeStepIndex) {
      // Guard client-only: compara contra `currentStep` (zustand), inaccesible en SSR.
      // react-doctor-disable-next-line react-doctor/nextjs-no-client-side-redirect
      router.replace(`/onboarding/${storeStep}`);
      return;
    }
    if (stepIndexFromUrl < storeStepIndex) {
      useOnboardingStore.getState().setStep(step);
    }
  }, [step, router]);

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
