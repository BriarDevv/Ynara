"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useUserStore } from "@/stores/user";

/**
 * Guard de entrada: redirige según onboarding completion.
 *
 * - Onboarding pendiente → `/onboarding` (que redirige a `/onboarding/auth`).
 * - Onboarding completado → placeholder de bienvenida acá mismo
 *   (hasta que exista `/home` en Sesión 5).
 *
 * **Importante**: si el user completó el onboarding, NO redirigimos a
 * `/onboarding`, porque `OnboardingLayout` reenvía a `/` cuando ve
 * `onboardingCompleted=true` — eso producía un loop infinito entre
 * `/` y `/onboarding`. Cuando exista `/home`, esta page redirigirá ahí
 * cuando completed=true.
 */
export default function RootPage() {
  const router = useRouter();
  const completed = useUserStore((s) => s.onboardingCompleted);

  useEffect(() => {
    if (!completed) {
      router.replace("/onboarding");
    }
    // TODO(Sesión 5): cuando exista `/home`, redirigir ahí si completed.
  }, [completed, router]);

  if (completed) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--color-bg-canvas)] px-6">
        <div className="flex max-w-[420px] flex-col items-center gap-3 text-center">
          <h1 className="text-title text-[var(--color-ink-deep)]">
            ¡Listo!
          </h1>
          <p className="text-body text-[var(--color-ink-soft)]">
            Tu perfil quedó guardado. La pantalla principal todavía está en
            construcción — volvé pronto.
          </p>
        </div>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-canvas)]">
      <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
    </div>
  );
}
