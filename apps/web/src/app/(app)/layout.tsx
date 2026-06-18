"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useOnboardingResumeStore } from "@/features/onboarding/resumeStore";
import { useUserStore } from "@/stores/user";

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
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!onboardingCompleted) {
      router.replace("/onboarding");
      return;
    }
    // Entramos a la app autenticada → ya no estamos resumiendo el onboarding;
    // limpiar el flag acá (mount-effect idempotente, safe bajo StrictMode, a
    // diferencia de un cleanup de unmount que se dispara en el doble-render).
    useOnboardingResumeStore.getState().setResuming(false);
    setChecked(true);
  }, [onboardingCompleted, router]);

  if (!checked) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--color-bg)]">
        <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
