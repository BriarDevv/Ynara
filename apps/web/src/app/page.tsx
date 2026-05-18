"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useUserStore } from "@/stores/user";

/**
 * Guard de entrada: redirige según onboarding completion.
 *
 * - Onboarding completado → /home (que se construye en Sesión 5).
 * - Onboarding pendiente → /onboarding (que redirige a /onboarding/auth).
 *
 * Mientras /home no exista (Sesión 5), redirigimos directo a /onboarding
 * en ambos casos para no romper. Se completa cuando merge la Sesión 5.
 */
export default function RootPage() {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    if (completed) {
      // TODO(Sesión 5): cambiar a /home cuando exista.
      router.replace("/onboarding");
    } else {
      router.replace("/onboarding");
    }
  }, [completed, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-soft)]">
      <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
    </div>
  );
}
