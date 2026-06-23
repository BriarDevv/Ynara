// Helper de View Transitions (DESIGN.md §8.3) con progressive
// enhancement: si el navegador no soporta la API o el usuario pidió menos
// movimiento, aplica el cambio sin animar. No es un hook (se puede llamar
// desde handlers); por eso lee la preferencia del DOM, no de React.

/**
 * Espejo de la cascada de `globals.css`: el override manual (clases del
 * store de a11y) gana sobre el OS-pref.
 */
function prefersReducedMotion(): boolean {
  if (typeof document === "undefined") return false;
  const html = document.documentElement;
  if (html.classList.contains("motion-off")) return true;
  if (html.classList.contains("motion-on")) return false;
  // Si `document` existe (guard de arriba), `window` también (DOM spec).
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Corre `update` dentro de una View Transition cuando se puede; si no hay
 * soporte o se pidió menos movimiento, lo corre directo (sin animación).
 */
export function startViewTransition(update: () => void): void {
  const supported = typeof document !== "undefined" && "startViewTransition" in document;

  if (!supported || prefersReducedMotion()) {
    update();
    return;
  }

  // Util de bajo nivel (no es un render de React ni un hook): se invoca desde
  // handlers con progressive enhancement. El componente <ViewTransition> de React
  // no aplica a un helper plano que solo envuelve un callback imperativo.
  // react-doctor-disable-next-line react-doctor/no-document-start-view-transition
  document.startViewTransition(update);
}
