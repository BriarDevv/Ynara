"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * ¿Matchea el `media query`? Pensado para breakpoints en runtime —
 * `useMediaQuery("(min-width: 768px)")` para distinguir desktop de mobile
 * cuando un cambio de layout necesita JS (p. ej. ocultar una vista del
 * switcher en mobile), no solo CSS responsive.
 *
 * SSR-safe: en server no hay `matchMedia`, así que el snapshot de servidor es
 * `false` (asumimos mobile-first) y el cliente corrige tras hidratar. Mismo
 * patrón que `useReducedMotion`: `useSyncExternalStore` con suscripción al
 * `change` del MediaQueryList.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );
  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
