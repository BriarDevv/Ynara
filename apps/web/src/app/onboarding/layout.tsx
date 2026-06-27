"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { LivingField } from "@/components/ui/LivingField";
import { OnboardingHeader } from "@/features/onboarding/components/OnboardingHeader";
import { ONBOARDING_STEPS, STEP_INDEX } from "@/features/onboarding/constants";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useUserStore } from "@/stores/user";

/**
 * Layout del flujo de onboarding.
 *
 * - Si el user ya completó onboarding → redirect a `/hoy` (la tab Hoy del
 *   app shell). Sin esto, un user con `onboardingCompleted=true` que tipea
 *   `/onboarding/*` cae en un 404 muerto.
 * - Header sticky con ProgressDots.
 * - El [step]/page renderiza el step actual; la prop `total/current`
 *   del ProgressDots las pasa cada step que usa StepShell (no las
 *   leo acá porque el layout no sabe en qué slug está cuando se renderiza
 *   con el componente padre del [step]).
 */
export default function OnboardingLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    // Completo → directo a la home real; `/hoy` exige onboardingCompleted, así
    // que no rebota (evita el salto extra por `/`).
    // Guard client-only: `completed` (zustand/localStorage) no existe en el
    // server; un redirect SSR no puede evaluar esta condición.
    // react-doctor-disable-next-line react-doctor/nextjs-no-client-side-redirect
    if (completed) router.replace("/hoy");
  }, [completed, router]);

  if (completed) return null;

  return (
    <div className="relative isolate flex min-h-screen flex-col">
      {/* Fondo vivo del onboarding (constellation: campo de nodos, la primera
          impresión — DESIGN.md §2.2). Absolute dentro del layout (isolate
          scopea su -z-10); modo default azul de marca: el usuario todavía no
          eligió modos. No interfiere con focus ni pointer. */}
      <LivingField variant="constellation" />
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
  const current = useOnboardingStore((s) => s.currentStep);
  const index = STEP_INDEX[current] ?? 0;

  return <OnboardingHeader total={ONBOARDING_STEPS.length} current={index} />;
}
