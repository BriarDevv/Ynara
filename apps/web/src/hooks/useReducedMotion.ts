"use client";

import { useSyncExternalStore } from "react";
import { useA11yStore } from "@/stores/a11y";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribeOS(onChange: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

function getOSReduced(): boolean {
  return window.matchMedia(QUERY).matches;
}

// En server no hay matchMedia: asumimos "no reduce" (deja animar) y el
// cliente corrige tras hidratar. Snapshot estable → sin loop en SSR.
function getServerSnapshot(): boolean {
  return false;
}

/**
 * ¿Debe reducirse el movimiento? Fuente de verdad espejada de la cascada
 * de `globals.css` (DESIGN.md §8.4): el override manual del store de a11y
 * gana sobre el OS-pref.
 *
 * - `motion: "reduce"` → siempre true (usuario forzó off).
 * - `motion: "normal"` → siempre false (usuario forzó on).
 * - `motion: "auto"`   → sigue `prefers-reduced-motion` del OS.
 *
 * Para gatear animaciones manejadas por JS. Las animaciones CSS ya las
 * gatea `globals.css` con las clases `.motion-on/.motion-off`.
 */
export function useReducedMotion(): boolean {
  const motion = useA11yStore((s) => s.motion);
  const osReduced = useSyncExternalStore(subscribeOS, getOSReduced, getServerSnapshot);

  if (motion === "reduce") return true;
  if (motion === "normal") return false;
  return osReduced;
}
