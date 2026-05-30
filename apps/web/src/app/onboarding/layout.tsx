"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { OnboardingHeader } from "@/features/onboarding/components/OnboardingHeader";
import { ONBOARDING_STEPS, STEP_INDEX } from "@/features/onboarding/constants";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useUserStore } from "@/stores/user";

/**
 * Layout del flujo de onboarding.
 *
 * - Si el user ya completó onboarding → redirect a /home.
 * - Header sticky con ProgressDots + skip-all.
 * - El [step]/page renderiza el step actual; el header lee `currentStep`
 *   del store para mantener ProgressDots sincronizado.
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

  const index = STEP_INDEX[current] ?? 0;

  const handleSkipAll = () => {
    // "Saltar onboarding" es una decisión deliberada de no completarlo
    // ahora (se retoma desde Ajustes). Marcamos `completed` para no
    // re-entrar al flujo en cada visita: sin esto, un skip antes del
    // Step de auth deja al user sin userId y la /home nunca flipea el
    // flag (queda en loop).
    reset();
    useUserStore.getState().completeOnboarding();
    router.replace("/home");
  };

  return (
    <OnboardingHeader total={ONBOARDING_STEPS.length} current={index} onSkipAll={handleSkipAll} />
  );
}
