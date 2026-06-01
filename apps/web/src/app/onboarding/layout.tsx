"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { BrandWaves } from "@/components/ui/BrandWaves";
import { OnboardingHeader } from "@/features/onboarding/components/OnboardingHeader";
import { ONBOARDING_STEPS, STEP_INDEX } from "@/features/onboarding/constants";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useUserStore } from "@/stores/user";

/**
 * Layout del flujo de onboarding.
 *
 * - Si el user ya completó onboarding → redirect a `/` (que vuelve a
 *   bounciar a `/onboarding`). TODO(Sesión 5): cambiar a `/home` cuando
 *   exista. Sin esto, un user con `onboardingCompleted=true` que tipea
 *   `/onboarding/*` cae en un 404 muerto.
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
    // TODO(Sesión 5): cambiar a "/home" cuando exista.
    if (completed) router.replace("/");
  }, [completed, router]);

  if (completed) return null;

  return (
    <div className="relative flex min-h-screen flex-col">
      {/* Velo de marca: ondas violet/blue suaves detrás de todo. Vive fixed
          inset-0 con z-negativo. No interfiere con focus ni pointer. */}
      <BrandWaves />
      <OnboardingHeaderWithProgress />
      <main className="flex flex-1 flex-col pb-12">{children}</main>
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
    reset();
    // TODO(Sesión 5): cambiar a "/home" cuando exista.
    router.replace("/");
  };

  return (
    <OnboardingHeader
      total={ONBOARDING_STEPS.length}
      current={index}
      onSkipAll={handleSkipAll}
    />
  );
}
