"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
import { cn } from "@/lib/cn";
import { useThemeStore } from "@/stores/theme";
import { isNavItemActive, NAV_ITEMS } from "./nav-items";

/**
 * Navegación principal del app shell, en dos chrome por breakpoint
 * (DESIGN.md §12, build-plan §3.1):
 *  - `MobileTabBar` (`<lg`): bottom-tab bar, hermano en flujo del `<main>`
 *    del shell (no fixed) — se ancla abajo en la columna de altura fija sin
 *    tapar el contenido (importa para el composer del chat).
 *  - `SidebarNav` (`lg+`): sidebar a la izquierda, estilo Claude/ChatGPT.
 *
 * Se monta uno por breakpoint con `display:none` (`hidden` / `lg:hidden`):
 * el oculto sale del árbol de accesibilidad, así no hay landmark
 * "Navegación principal" duplicado.
 */

export function MobileTabBar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Navegación principal"
      className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg)]/85 backdrop-blur-md lg:hidden"
    >
      <ul className="mx-auto flex max-w-[640px] items-stretch justify-around px-2 pb-[env(safe-area-inset-bottom)]">
        {NAV_ITEMS.map((item) => {
          const active = isNavItemActive(pathname, item.href);
          return (
            <li key={item.id} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-[56px] flex-col items-center justify-center gap-1 rounded-[var(--radius-md)] py-2 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                  active
                    ? "text-[var(--color-ink)]"
                    : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
                )}
              >
                <Icon name={item.icon} size={24} strokeWidth={active ? 2.6 : 2.2} />
                <span className="text-caption">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function SidebarNav() {
  const pathname = usePathname();
  // El lockup se elige por fondo (§11.1): color sobre el sidebar claro,
  // mono-light cuando el tema es Noche (el símbolo a color perdería contraste).
  // `mounted` evita el hydration mismatch: el server siempre renderiza light
  // (no hay localStorage), así que el primer paint del cliente también usa
  // `color`; recién tras montar leemos el tema persistido. Mismo espíritu que
  // el ThemeApplier (providers.tsx). El flash es un detalle decorativo.
  const dark = useThemeStore((s) => s.theme === "dark");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const wordmarkVariant = mounted && dark ? "mono-light" : "color";
  return (
    <nav
      aria-label="Navegación principal"
      className="hidden h-full w-[240px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-6 lg:flex"
    >
      {/* Lockup oficial (§11.1): YnaraWordmark con baseline compartida, en vez
          del símbolo + span armado a mano. El Link lleva su propio aria-label
          ("Ynara — ir a Hoy"), que es el que nombra el control; el role=img
          del wordmark no se concatena al nombre del Link (un aria-label
          explícito en el ancestro lo gana), así que no hay doble anuncio. */}
      <Link href="/hoy" aria-label="Ynara — ir a Hoy" className="mb-6 flex px-2">
        <YnaraWordmark height={28} variant={wordmarkVariant} />
      </Link>
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = isNavItemActive(pathname, item.href);
          return (
            <li key={item.id}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-button transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
                  active
                    ? "bg-[var(--color-bg-soft)] text-[var(--color-ink)]"
                    : "text-[var(--color-ink-soft)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]",
                )}
              >
                <Icon name={item.icon} size={22} strokeWidth={active ? 2.6 : 2.2} />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
