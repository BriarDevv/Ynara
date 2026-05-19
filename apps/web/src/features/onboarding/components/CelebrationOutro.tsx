"use client";

import { useEffect } from "react";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { useA11yStore } from "@/stores/a11y";

type Props = {
  /** Se llama una vez transcurrida la animación (o inmediatamente si motion=reduce). */
  onComplete: () => void;
};

const HOLD_MS = 1500;

/**
 * Pantalla outro mostrada después de cerrar el onboarding.
 *
 * - Mark Ynara grande, centrado, con `anim-pulse-violet` (keyframe en
 *   `motion.css`) durante 1.5s.
 * - Si el usuario pidió `motion=reduce` (o el OS lo pide y no hay override),
 *   se omite la animación y el mark se muestra estático.
 * - El parent maneja el unmount via `onComplete` (típicamente navegando
 *   a `/?welcome=true` — TODO(Sesión 5): cambiar a `/home`).
 */
export function CelebrationOutro({ onComplete }: Props) {
  const motion = useA11yStore((s) => s.motion);

  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const reduceMotion =
    motion === "reduce" || (motion === "auto" && prefersReducedMotion);

  useEffect(() => {
    const timer = window.setTimeout(onComplete, HOLD_MS);
    return () => window.clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="mx-auto flex min-h-[80vh] w-full max-w-[480px] flex-1 flex-col items-center justify-center gap-8 px-6 py-12 text-center">
      <YnaraMark size={96} className={reduceMotion ? undefined : "anim-pulse-violet"} />
      <p className="text-title">Listo, te estoy esperando.</p>
    </div>
  );
}
