"use client";

import { useEffect } from "react";
import { useUserStore } from "@/stores/user";

/**
 * Home — placeholder de Sesión 4.
 *
 * Cierra el onboarding: si llegamos con un perfil cargado pero el flag
 * `onboardingCompleted` todavía en false (lo difiere el CelebrationOutro
 * para no romper su animación), lo marcamos acá, ya fuera del árbol del
 * onboarding. La home real (Greeting, recomendaciones, etc.) llega en
 * Sesión 5.
 */
export default function HomePage() {
  const userId = useUserStore((s) => s.userId);
  const displayName = useUserStore((s) => s.displayName);
  const completed = useUserStore((s) => s.onboardingCompleted);
  const completeOnboarding = useUserStore((s) => s.completeOnboarding);

  useEffect(() => {
    if (userId && !completed) completeOnboarding();
  }, [userId, completed, completeOnboarding]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[480px] flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <h1 className="text-title">{displayName ? `Hola, ${displayName}` : "Hola"}</h1>
      <p className="text-body text-[var(--color-ink-soft)]">
        Tu home llega en la próxima entrega. Por ahora, el onboarding ya quedó listo.
      </p>
    </main>
  );
}
