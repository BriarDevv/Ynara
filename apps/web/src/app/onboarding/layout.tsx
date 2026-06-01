"use client";

import { GrainOverlay, MemoryField } from "@ynara/ui";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef } from "react";
import { OnboardingHeader } from "@/features/onboarding/components/OnboardingHeader";
import { ONBOARDING_STEPS, STEP_INDEX } from "@/features/onboarding/constants";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useUserStore } from "@/stores/user";

/**
 * Layout del flujo de onboarding.
 *
 * - Si el user **llegó** ya completado (tipeó `/onboarding/*` de más) →
 *   redirect a `/hoy`. Sin esto cae en un 404 muerto. El check se hace con
 *   el valor capturado al montar (no el live): si el flag se flipea DURANTE
 *   el flujo (outro / skip-all), no disparamos un redirect que competiría
 *   con —y pisaría el query param de— la navegación del propio outro.
 * - Header sticky con ProgressDots + skip-all.
 * - El [step]/page renderiza el step actual; la prop `total/current`
 *   del ProgressDots las pasa cada step que usa StepShell (no las
 *   leo acá porque el layout no sabe en qué slug está cuando se renderiza
 *   con el componente padre del [step]).
 */
export default function OnboardingLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  // Valor al montar: distingue "llegó completado" de "completó durante el
  // flujo" (ver doc arriba). El segundo caso lo navega el outro/skip-all.
  const completedOnMount = useRef(useUserStore.getState().onboardingCompleted);

  useEffect(() => {
    if (completedOnMount.current) router.replace("/hoy");
  }, [router]);

  if (completedOnMount.current) return null;

  return (
    <div className="relative isolate min-h-screen bg-[var(--color-bg-soft)]">
      {/* Ambiente de marca detrás de todo el flujo: la "Red de memoria" como
          fondo + grano (§2/§3.6). Decorativo, no captura punteros. `isolate`
          crea el stacking context que scopea los z-index acá; `-z-10` deja la
          capa detrás del header y el contenido. El `overflow-hidden` vive en
          esta capa (no en el root) para clipear el SVG `slice` sin matar el
          scroll del documento en steps altos (forms en viewports chicos). */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <MemoryField density="dispersa" />
        <GrainOverlay />
      </div>
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
    // Step de auth deja al user sin userId y nunca se flipea el flag.
    reset();
    useUserStore.getState().completeOnboarding();
    router.replace("/hoy");
  };

  return (
    <OnboardingHeader total={ONBOARDING_STEPS.length} current={index} onSkipAll={handleSkipAll} />
  );
}
