"use client";

import { Icon } from "@ynara/ui";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { applyThemeClass, useThemeStore } from "@/stores/theme";

/**
 * Toggle de tema del topbar (blueprint §2.1): alterna Noche (`theme-dark`) y
 * marfil. Botón ghost con ícono del set propio. Aplica `applyThemeClass` en el
 * mismo click (además del `ThemeApplier` del provider) para que el cambio sea
 * inmediato. `mounted` evita el mismatch de hidratación: el server siempre
 * renderiza el default (Noche) porque no conoce localStorage.
 */
export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const dark = mounted && theme === "dark";
  const nextLabel = dark ? "Cambiar a tema claro" : "Cambiar a tema Noche";

  return (
    <button
      type="button"
      aria-label={nextLabel}
      title={nextLabel}
      onClick={() => {
        toggleTheme();
        applyThemeClass({ theme: dark ? "light" : "dark" });
      }}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]",
      )}
    >
      {/* `foco` (diamante) para Noche, `idea` (bombilla) para claro: acento de marca, no emoji. */}
      <Icon name={dark ? "idea" : "foco"} size={20} strokeWidth={2.2} />
    </button>
  );
}
