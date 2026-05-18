"use client";

import { useEffect } from "react";
import type { OnboardingStep } from "@/features/onboarding/constants";
import { AuthStep } from "@/features/onboarding/steps/AuthStep";
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
 * "no podés saltar steps por URL manipulada" se hará en Sesión 4
 * cuando aparezcan los steps que dependen de auth.
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
    case "modos":
    case "a11y":
      return <ComingInSession4 step={step} />;
  }
}

function ComingInSession4({ step }: { step: string }) {
  return (
    <div className="anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-4 px-6 py-12 text-center">
      <h1 className="text-title">Próximamente</h1>
      <p className="text-body text-[var(--color-ink-soft)]">
        Step <code>{step}</code> llega en Sesión 4 del plan (mood + modos + a11y + outro).
      </p>
    </div>
  );
}
