"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
import { useThemeStore } from "@/stores/theme";
import { AdminMenu } from "./AdminMenu";
import { NAV_ITEMS } from "./nav-items";
import { PerimeterBadge } from "./PerimeterBadge";
import { RangeSelector } from "./RangeSelector";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Topbar del panel (blueprint §2.1): barra glass sticky en `z-topbar` con
 * hairline inferior. A izquierda el lockup oficial + divider + breadcrumb del
 * destino actual; a derecha, en `gap-4`: el `PerimeterBadge` compacto (firma de
 * soberanía siempre visible), el `RangeSelector` global, el `ThemeToggle` y la
 * identidad admin (Diamond outline + display_name).
 *
 * El estado del perímetro es `intact` por default mientras no haya endpoint
 * `/overview` cableado (no se inventa un estado distinto al real verificable).
 *
 * La identidad admin es ahora el `AdminMenu` (Diamond + display_name como
 * disclosure con "Cerrar sesión"); el displayName lo provee el admin store.
 */

/** Deriva el label del breadcrumb desde el pathname y la IA de navegación. */
function useBreadcrumb(pathname: string): string {
  for (const group of NAV_ITEMS) {
    for (const item of group.items) {
      if (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)) {
        return item.label;
      }
    }
  }
  return "Panel";
}

export function Topbar() {
  const pathname = usePathname();
  const crumb = useBreadcrumb(pathname);

  // Lockup por fondo: mono-light sobre Noche, color sobre claro. `mounted` evita
  // el mismatch (el server siempre renderiza el default Noche, sin localStorage).
  const dark = useThemeStore((s) => s.theme === "dark");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const wordmarkVariant = mounted && dark ? "mono-light" : "color";

  return (
    <header className="sticky top-0 z-[var(--z-topbar)] flex h-16 items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-glass)] px-6 backdrop-blur-md">
      {/* Izquierda: lockup + divider + breadcrumb. */}
      <div className="flex min-w-0 items-center gap-3">
        <YnaraWordmark height={24} variant={wordmarkVariant} />
        <span aria-hidden className="h-5 w-px bg-[var(--color-border)]" />
        <nav aria-label="Ubicación" className="min-w-0">
          <span className="truncate text-caption text-[var(--color-ink-soft)]">{crumb}</span>
        </nav>
      </div>

      {/* Derecha: firma de soberanía, rango, tema, identidad. */}
      <div className="ml-auto flex items-center gap-4">
        <span className="max-md:hidden">
          <PerimeterBadge variant="compact" status="intact" />
        </span>
        <RangeSelector />
        <ThemeToggle />
        <AdminMenu />
      </div>
    </header>
  );
}
