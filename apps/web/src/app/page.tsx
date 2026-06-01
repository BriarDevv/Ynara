"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useUserStore } from "@/stores/user";

/**
 * Guard de entrada: redirige según onboarding completion.
 *
 * - Onboarding completado → /hoy.
 * - Onboarding pendiente → /onboarding (que redirige a /onboarding/auth).
 */
export default function RootPage() {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    router.replace(completed ? "/hoy" : "/onboarding");
  }, [completed, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-soft)]">
      <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
    </div>
  );
}
