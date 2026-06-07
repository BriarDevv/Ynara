"use client";

import { Icon } from "@ynara/ui";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
import { cn } from "@/lib/cn";
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
                    : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink-soft)]",
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
  return (
    <nav
      aria-label="Navegación principal"
      className="hidden h-full w-[240px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-6 lg:flex"
    >
      {/* Lockup oficial (§11.1): YnaraWordmark con baseline compartida, en
          vez del símbolo + span armado a mano. El aria-label del Link nombra
          el destino; el wordmark queda decorativo dentro (no duplica). */}
      <Link href="/hoy" aria-label="Ynara — ir a Hoy" className="mb-6 flex px-2">
        <YnaraWordmark height={28} className="text-[var(--color-ink)]" />
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
