"use client";

import { usePathname } from "next/navigation";

/**
 * `true` cuando estamos bajo la ruta del deck (`/presentacion`).
 *
 * El layout raíz monta el chrome del sitio (campo WebGL conducido por scroll,
 * Lenis, preloader, nav, footer) para TODAS las rutas. La presentación es un
 * pitch a pantalla completa navegado por teclado: no debe heredar nada de eso
 * (montaría un segundo contexto WebGL, Lenis pelearía con la navegación por
 * láminas, etc.). Cada pieza de chrome usa este hook para auto-suprimirse ahí.
 * En `/` el path no matchea → la landing queda intacta.
 */
export function useIsDeckRoute(): boolean {
  const pathname = usePathname();
  return pathname?.startsWith("/presentacion") ?? false;
}
