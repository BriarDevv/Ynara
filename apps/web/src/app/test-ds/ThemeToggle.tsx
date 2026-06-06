"use client";

import { useThemeStore } from "@/stores/theme";

/**
 * Switch claro ↔ Noche del sandbox (DESIGN.md §3.1). Escribe directo al
 * store de tema (persiste en `ynara.theme`); el ThemeApplier global hace
 * el resto. Vive solo en /test-ds hasta que exista la pantalla de ajustes.
 */
export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggleTheme}
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
