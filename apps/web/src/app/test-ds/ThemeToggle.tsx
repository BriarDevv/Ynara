"use client";

import { startViewTransition } from "@/lib/viewTransition";
import { useThemeStore } from "@/stores/theme";

/**
 * Switch claro ↔ Noche del sandbox (DESIGN.md §3.1). Escribe directo al
 * store de tema (persiste en `ynara.theme`); el ThemeApplier global hace
 * el resto. Vive solo en /test-ds hasta que exista la pantalla de ajustes.
 *
 * El cambio va envuelto en `startViewTransition` (§8.3 / §16 #8): el toggle de
 * tema es un update **síncrono** del DOM (el ThemeApplier togglea `theme-dark`
 * al instante vía un subscriber del store, y los tokens `--color-*` reculean),
 * justo el caso donde la View Transitions API hace un crossfade root
 * claro↔Noche limpio. El helper degrada solo (sin soporte o con reduced-motion
 * aplica el cambio sin animar).
 *
 * Nota: lo que cambia por **re-render de React** (variante del wordmark, tinte
 * del LivingField) queda fuera del snapshot —React renderiza después de que el
 * callback retorna— y aparece justo tras el crossfade. Es sutil y aceptable
 * acá; si molesta al migrar a la pantalla de ajustes real, un `flushSync`
 * adentro del update lo mete en el snapshot.
 */
export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={() => startViewTransition(toggleTheme)}
      // Nombre accesible ESTABLE (la acción): el estado lo porta
      // aria-pressed, no el nombre — el texto visible sí muestra el tema.
      aria-label="Cambiar tema"
      aria-pressed={dark}
      className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-2 text-body-sm text-[var(--color-ink)] transition-[border-color,background-color] duration-[var(--duration-fast)] hover:border-[var(--color-border-strong)]"
    >
      <span
        aria-hidden
        className="h-2 w-2 rounded-[var(--radius-pill)]"
        style={{ backgroundColor: dark ? "var(--color-lavanda)" : "var(--color-azul)" }}
      />
      {dark ? "Tema: Noche" : "Tema: claro"}
    </button>
  );
}
