"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { useUserStore } from "@/stores/user";
import { useCompleteOnboarding } from "../hooks/useCompleteOnboarding";

/** Duración mínima del outro antes de entrar al home (plan §4.7). */
const OUTRO_MIN_MS = 1500;

/**
 * Cierre de marca del onboarding. Dispara la mutation de onboard, muestra
 * el YnaraMark pulsando (incluye el diamond violeta — símbolo de memoria)
 * y, cuando el backend confirma y pasó el tiempo mínimo, hace fade a
 * `/hoy` con `?welcome=true`.
 *
 * Si la mutation falla, no deja al usuario varado: muestra un error humano
 * con opción de reintentar.
 */
export function CelebrationOutro() {
  const router = useRouter();
  const { complete, isPending, isError, isSuccess, clearDraft } = useCompleteOnboarding();
  const [minElapsed, setMinElapsed] = useState(false);
  const navigatedRef = useRef(false);

  // Dispara la mutation al montar. NO usamos un ref-guard "fire once": en
  // StrictMode (dev) el efecto corre dos veces y react-query crea un
  // observer nuevo en el segundo mount; un ref que sobreviva al remount
  // bloquearía el mutate() del observer vivo y la mutation quedaría pending
  // para siempre (isSuccess nunca true → nunca navega). `complete` es
  // estable (useCallback), así que en prod este efecto corre una sola vez;
  // el doble disparo en dev es inofensivo (el onboard mockeado es idempotente).
  useEffect(() => {
    complete();
  }, [complete]);

  // Timer mínimo de la animación — independiente del ciclo de la mutation,
  // para que el outro dure siempre OUTRO_MIN_MS desde que se monta.
  useEffect(() => {
    const timer = window.setTimeout(() => setMinElapsed(true), OUTRO_MIN_MS);
    return () => window.clearTimeout(timer);
  }, []);

  // Navega cuando el backend confirmó y ya pasó la animación mínima.
  //
  // Acá flipeamos `onboardingCompleted` (antes se difería a la home): el
  // guard del route group `(app)` exige el flag en true para montar `/hoy`,
  // así que tiene que estar seteado ANTES de navegar. Hacerlo ahora — con la
  // animación ya terminada y saliendo del árbol del onboarding — no desmonta
  // el outro a destiempo (el problema que motivaba el deferral original).
  useEffect(() => {
    if (navigatedRef.current) return;
    if (isSuccess && minElapsed) {
      navigatedRef.current = true;
      useUserStore.getState().completeOnboarding();
      router.replace("/hoy?welcome=true");
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
            // Reseteamos navigatedRef para permitir navegar tras el reintento
            // exitoso, y volvemos a disparar la mutation.
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
      {/* Pieza editorial de cierre: big type (§4) sobre el ambiente de la
          "Red de memoria" que ya provee el layout (no se duplica el field). */}
      <p className="text-display text-balance text-[var(--color-ink)]">
        Listo, te estoy esperando.
      </p>
    </div>
  );
}
