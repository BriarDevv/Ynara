"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { useCompleteOnboarding } from "../hooks/useCompleteOnboarding";

/** Duración mínima del outro antes de entrar al home (plan §4.7). */
const OUTRO_MIN_MS = 1500;

/**
 * Cierre de marca del onboarding. Dispara la mutation de onboard, muestra
 * el YnaraMark pulsando (incluye el diamond violeta — símbolo de memoria)
 * y, cuando el backend confirma y pasó el tiempo mínimo, hace fade al
 * /home con `?welcome=true`.
 *
 * Si la mutation falla, no deja al usuario varado: muestra un error humano
 * con opción de reintentar.
 */
export function CelebrationOutro() {
  const router = useRouter();
  const { complete, isPending, isError, isSuccess, clearDraft } = useCompleteOnboarding();
  const [minElapsed, setMinElapsed] = useState(false);
  const firedOnMountRef = useRef(false);
  const navigatedRef = useRef(false);

  // Dispara la mutation una sola vez al montar. `complete` es estable
  // (useCallback en el hook), así que este effect no se re-ejecuta.
  useEffect(() => {
    if (firedOnMountRef.current) return;
    firedOnMountRef.current = true;
    complete();
  }, [complete]);

  // Timer mínimo de la animación — independiente del ciclo de la mutation,
  // para que el outro dure siempre OUTRO_MIN_MS desde que se monta.
  useEffect(() => {
    const timer = window.setTimeout(() => setMinElapsed(true), OUTRO_MIN_MS);
    return () => window.clearTimeout(timer);
  }, []);

  // Navega cuando el backend confirmó y ya pasó la animación mínima.
  useEffect(() => {
    if (navigatedRef.current) return;
    if (isSuccess && minElapsed) {
      navigatedRef.current = true;
      router.replace("/home?welcome=true");
      clearDraft();
    }
  }, [isSuccess, minElapsed, router, clearDraft]);

  if (isError) {
    return (
      <div className="anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col items-center justify-center gap-6 px-6 py-16 text-center">
        <h1 className="text-title">Casi…</h1>
        <p className="text-body text-[var(--color-ink-soft)]">
          No pude guardar tu perfil. Puede ser la conexión. Probá de nuevo.
        </p>
        <Button
          onClick={() => {
            // Sólo reseteamos navigatedRef: firedOnMountRef guarda el
            // disparo de mount, acá llamamos complete() directo.
            navigatedRef.current = false;
            complete();
          }}
          disabled={isPending}
        >
          {isPending ? "Reintentando…" : "Reintentar"}
        </Button>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="anim-fade-in mx-auto flex w-full max-w-[480px] flex-1 flex-col items-center justify-center gap-8 px-6 py-16 text-center"
    >
      <YnaraMark size={120} className="anim-pulse-soft" title="Ynara" />
      <p className="text-subtitle text-[var(--color-ink)]">Listo, te estoy esperando.</p>
    </div>
  );
}
