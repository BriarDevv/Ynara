import { type A11yState, createA11yStore } from "@ynara/core/stores";
import { clientStorage } from "@/lib/clientStorage";

// Instancia del panel del store de a11y (ADR-012): el estado y las acciones
// viven en @ynara/core; acá se inyecta el storage SSR-safe. `applyA11yClasses`
// es app-only (togglea clases en <html>) y se queda en esta app.
export const useA11yStore = createA11yStore(clientStorage);

export type { A11yState, MotionPreference, TextSize } from "@ynara/core/stores";

/**
 * Aplica el estado actual de a11y a las clases del <html>.
 * Llamar desde un componente client después de hidratar.
 */
export function applyA11yClasses(state: A11yState): void {
  if (typeof document === "undefined") return;
  const html = document.documentElement;

  html.classList.remove("text-size-sm", "text-size-md", "text-size-lg");
  html.classList.add(`text-size-${state.textSize}`);

  html.classList.toggle("theme-high-contrast", state.highContrast);

  html.classList.remove("motion-off", "motion-on");
  if (state.motion === "reduce") html.classList.add("motion-off");
  else if (state.motion === "normal") html.classList.add("motion-on");
}
