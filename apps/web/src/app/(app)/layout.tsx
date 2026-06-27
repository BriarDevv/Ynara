"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";
import { AppShell } from "@/components/AppShell";
import { useUserStore } from "@/stores/user";

// Suscripción a la rehidratación del store de usuario vía useSyncExternalStore:
// el snapshot inicial sale directo (sin effect de mount → sin render extra
// vacío), y el server siempre reporta "no hidratado" (SSR no tiene localStorage).
const subscribeHydration = (onChange: () => void) =>
  useUserStore.persist.onFinishHydration(onChange);
const getHydratedSnapshot = () => useUserStore.persist.hasHydrated();
const getHydratedServerSnapshot = () => false;

/**
 * Layout del route group `(app)`: envuelve todas las vistas autenticadas
 * (Hoy, Chat, Agenda, Tú, …) con el app shell y centraliza el guard de
 * onboarding (build-plan §3.1).
 *
 * Un user sin onboarding completo que entra a cualquier ruta del grupo cae
 * a `/onboarding`. El check corre en cliente (el flag vive en localStorage
 * vía zustand persist, el server no lo conoce) y gatea el render hasta
 * validar, para no flashear el shell antes del redirect — mismo patrón que
 * el ex-`ChatRoute`.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);

  // Esperar a que zustand REHIDRATE desde localStorage antes de evaluar el guard.
  // En un reload DURO el store arranca en initialState (`onboardingCompleted=false`)
  // y la persistencia rehidrata async; sin esperarla, el guard redirige a
  // `/onboarding` por error a un user que SÍ está onboardeado (race de hidratación,
  // mismo que afectaba al token en `lib/api.ts`). `hasHydrated()` cubre el caso ya
  // hidratado (nav cliente); `onFinishHydration` el reload en frío. Leído vía
  // useSyncExternalStore: valor inicial directo (sin render vacío de arranque) y
  // SSR-safe (snapshot de server = no hidratado).
  const hydrated = useSyncExternalStore(
    subscribeHydration,
    getHydratedSnapshot,
    getHydratedServerSnapshot,
  );

  // `allowed` (render del shell) se DERIVA del estado, no se guarda como state
  // encadenado: evita el render extra entre commits. El gate sigue tapando el
  // shell hasta validar (no flashea el shell antes del redirect).
  const allowed = hydrated && onboardingCompleted;

  useEffect(() => {
    if (!hydrated) return;
    if (!onboardingCompleted) {
      // Guard client-only: `onboardingCompleted` vive en localStorage (zustand);
      // el server no lo conoce, un redirect SSR no puede evaluar este guard.
      // react-doctor-disable-next-line react-doctor/nextjs-no-client-side-redirect
      router.replace("/onboarding");
    }
  }, [hydrated, onboardingCompleted, router]);

  if (!allowed) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--color-bg)]">
        <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
