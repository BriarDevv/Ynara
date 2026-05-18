"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { OnboardingHeader } from "@/features/onboarding/components/OnboardingHeader";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useUserStore } from "@/stores/user";

/**
 * Layout del flujo de onboarding.
 *
 * - Si el user ya completó onboarding → redirect a /home.
 * - Header sticky con ProgressDots + skip-all.
 * - El [step]/page renderiza el step actual; la prop `total/current`
 *   del ProgressDots las pasa cada step que usa StepShell (no las
 *   leo acá porque el layout no sabe en qué slug está cuando se renderiza
 *   con el componente padre del [step]).
 */
export default function OnboardingLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    if (completed) router.replace("/home");
  }, [completed, router]);

  if (completed) return null;

  return (
    <div className="min-h-screen bg-[var(--color-bg-soft)]">
      <OnboardingHeaderWithProgress />
      <main className="flex flex-col">{children}</main>
    </div>
  );
}

/**
 * Lee el step actual del store para alimentar el ProgressDots del header.
 * Vive como sub-componente para evitar re-mounts del layout cuando cambia
 * el step.
 */
function OnboardingHeaderWithProgress() {
  const router = useRouter();
  const reset = useOnboardingStore((s) => s.reset);
  const current = useOnboardingStore((s) => s.currentStep);

  // STEP_INDEX viene de constants.ts pero importarlo crearía un ciclo de
  // imports con el feature. Lo replico acá (5 steps fijos por contrato).
  const STEP_TO_INDEX: Record<string, number> = {
    auth: 0,
    nombre: 1,
    dia: 2,
    modos: 3,
    a11y: 4,
  };
  const index = STEP_TO_INDEX[current] ?? 0;

  const handleSkipAll = () => {
    reset();
    router.replace("/home");
  };

  return <OnboardingHeader total={5} current={index} onSkipAll={handleSkipAll} />;
}
