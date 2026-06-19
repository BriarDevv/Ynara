import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemePreference = "light" | "dark";

type ThemeState = {
  /**
   * Tema visual del panel (DESIGN.md §3.1): marfil (light) o Noche (dark).
   * Default Noche: el panel es una herramienta interna de uso prolongado y el
   * mockup canónico es dark-first. Decisión del usuario vía store — sin depender
   * de `prefers-color-scheme`.
   */
  theme: ThemePreference;
};

type ThemeActions = {
  setTheme: (theme: ThemePreference) => void;
  toggleTheme: () => void;
  reset: () => void;
};

const initialState: ThemeState = {
  // Noche por default (paridad con el web dark-first). El usuario puede pasar a
  // claro desde el switcher; persiste su elección.
  theme: "dark",
};

/**
 * Store de tema propio del panel: clon del modelo del web, persistido con la
 * key `ynara.theme` (el pre-paint en `app/a11y-init.ts` lee esta misma key).
 */
export const useThemeStore = create<ThemeState & ThemeActions>()(
  persist(
    (set) => ({
      ...initialState,
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
      reset: () => set(initialState),
    }),
    { name: "ynara.theme" },
  ),
);

/**
 * Aplica el tema actual al <html> (clase `theme-dark` + `data-theme`).
 * Llamar desde un componente client después de hidratar; el pre-paint
 * (`app/a11y-init.ts`) hace lo mismo antes del primer paint.
 */
export function applyThemeClass(state: ThemeState): void {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  html.classList.toggle("theme-dark", state.theme === "dark");
  html.dataset.theme = state.theme;
}
