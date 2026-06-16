"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useUserStore } from "@/stores/user";

/**
 * Guard de entrada: redirige según el estado del onboarding.
 *
 * - Onboarding pendiente → `/onboarding` (que reenvía a `/onboarding/auth`).
 * - Onboarding completado → `/hoy` (tab Hoy dentro del app shell).
 *
 * **Sin loop**: `/hoy` vive en el route group `(app)`, cuyo layout exige
 * `onboardingCompleted`. Un user completo nunca vuelve a `/onboarding` (que
 * sí reenvía a `/` al ver `onboardingCompleted=true`), así que la redirección
 * `/ → /hoy` es estable y no reintroduce el ciclo `/ ↔ /onboarding`.
 */
export default function RootPage() {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    router.replace(completed ? "/hoy" : "/onboarding");
  }, [completed, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-canvas)]">
      <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
    </div>
  );
}
