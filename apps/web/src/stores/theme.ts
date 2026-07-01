import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemePreference = "light" | "dark" | "system";

type ThemeState = {
  /**
   * Tema visual de la app (DESIGN.md §3.1): marfil (light), Noche (dark, default)
   * o `system` (sigue `prefers-color-scheme` del SO). `light`/`dark` son una
   * decisión explícita del usuario; `system` delega en el SO y reacciona en vivo
   * a sus cambios (ver `ThemeApplier` en providers.tsx).
   */
  theme: ThemePreference;
};

type ThemeActions = {
  setTheme: (theme: ThemePreference) => void;
  toggleTheme: () => void;
  reset: () => void;
};

const initialState: ThemeState = {
  // Noche por default (paridad con el mockup canónico, que es dark-first).
  // El usuario puede pasar a claro desde el switcher; persiste su elección.
  theme: "dark",
};

/**
 * Store de tema propio (§16 #4): clon del modelo de `stores/a11y.ts`,
 * deliberadamente separado — extender el store de a11y arrastraría el
 * mirror del draft de onboarding y su `reset()`.
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
 * Resuelve la preferencia a un tema EFECTIVO (`light`/`dark`). `system` mira
 * `prefers-color-scheme`; sin `matchMedia` (SSR / jsdom) cae a `dark` (el
 * default dark-first), así nunca rompe ni hace flash.
 */
export function resolveEffectiveTheme(theme: ThemePreference): "light" | "dark" {
  if (theme !== "system") return theme;
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Aplica el tema EFECTIVO al <html> (clase `theme-dark` + `data-theme`). El CSS
 * solo entiende `light`/`dark`, así que `system` se resuelve antes; la
 * preferencia `system` vive solo en el store (para saber qué pill marcar).
 * Llamar desde un componente client después de hidratar; el pre-paint
 * (`app/a11y-init.ts`) hace lo mismo antes del primer paint.
 */
export function applyThemeClass(state: ThemeState): void {
  if (typeof document === "undefined") return;
  const effective = resolveEffectiveTheme(state.theme);
  const html = document.documentElement;
  html.classList.toggle("theme-dark", effective === "dark");
  html.dataset.theme = effective;
}
